
import optuna
import argparse
from functools import partial
from pytorch_lightning import Trainer, LightningModule, seed_everything
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.callbacks import Callback
from pytorch_lightning.callbacks.early_stopping import EarlyStopping

from text_classification.datamodule import DataModule
from text_classification.datasets import SSTDataset
from text_classification.encoders import RNFEncoder
from text_classification.models import RNF
from text_classification.tokenizers import SpacyTokenizer
from text_classification.vectors import GloVe
from text_classification.vocab import Vocab

class OptunaCallback(Callback):

    def __init__(self, trial: optuna.trial.Trial, monitor: str) -> None:

        self.trial = trial
        self.monitor = monitor


    def on_epoch_end(self, trainer: Trainer, pl_module: LightningModule) -> None:

        metrics = trainer.callback_metrics
        epoch = trainer.current_epoch

        current_score = metrics.get(self.monitor)
        self.trial.report(current_score, step=epoch)
        if self.trial.should_prune():
            message = "Trial was pruned at epoch {}.".format(epoch)
            raise optuna.TrialPruned(message)

 
def objective(trial, args):

    seed_everything(42)

    if not args.fine_grained:
        filter_func = lambda x: x.label != "neutral"
    else:
        filter_func = None

    # 1. Get SST dataset
    train, val, test = SSTDataset(filter_func=filter_func, tokenizer=SpacyTokenizer(), 
            train_subtrees=True, fine_grained=args.fine_grained
    )

    # 2. Get vocab
    vocab = Vocab(train)

    # 3. Retrieve pre-trained embeddings
    vectors = GloVe(name="840B", dim=300)
    embed_mat = vectors.get_matrix(vocab)

    # 4. Setup encoder to encode examples
    encoder = RNFEncoder(vocab=vocab, target_encoding={"negative": 0, "positive": 1})

    # 5. Setup train, val and test dataloaders
    ds = DataModule(
        train=train,
        val=val,
        test=test,
        encoder=encoder,
        batch_size=trial.suggest_int("batch_size", 16, 64),
    )

    # 6. Setup model
    num_class = 5 if args.fine_grained else 2
    model = RNF(
        input_size=len(vocab),
        num_class=num_class,
        embed_mat=embed_mat,
        filter_width=trial.suggest_int("filter_width", 5, 8),
        embed_dropout=trial.suggest_float("embed_dropout", 0.2, 0.4),
        dropout=trial.suggest_float("dropout", 0.2, 0.4),
        lr=trial.suggest_float("lr", 0.0001, 0.001)
    )

    # 7. Setup trainer
    early_stop_callback = EarlyStopping(
        monitor="val_epoch_loss",
        min_delta=0.0001,
        patience=3,
        verbose=False,
        mode="min",
    )

    checkpoint_callback = ModelCheckpoint(
        filepath="./checkpoints/" + "{epoch}",
        save_top_k=1,
        verbose=False,
        monitor="val_epoch_loss",
        mode="min",
    )

    trainer = Trainer(
        checkpoint_callback=checkpoint_callback,
        callbacks=[OptunaCallback(trial, "val_epoch_loss"), early_stop_callback],
        gpus=1, progress_bar_refresh_rate=0, max_epochs=15, deterministic=True
    )

    # 8. Fit model
    trainer.fit(model, ds.train_dataloader(), ds.val_dataloader())

    # 9. Test model
    results = trainer.test(
        model, ds.val_dataloader(), ckpt_path=checkpoint_callback.best_model_path
    )

    return results['test_epoch_loss']


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fine_grained", action = "store_true")
    args = parser.parse_args()

    objective = partial(objective, args=args)

    pruner = optuna.pruners.MedianPruner()

    study = optuna.create_study(direction="minimize", pruner=pruner)
    study.optimize(objective, n_trials=30, timeout=1200)

    print("Best trial:")
    trial = study.best_trial

    print("  Value: {}".format(trial.value))

    print("  Params: ")
    for key, value in trial.params.items():
        print("    {}: {}".format(key, value))
