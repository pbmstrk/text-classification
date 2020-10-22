from typing import Optional, Callable
from ..datasets import TextDataset

from torch.utils.data import DataLoader


class DataModule:
    def __init__(
        self,
        train: TextDataset,
        encoder: Callable,
        val: Optional[TextDataset] = None,
        test: Optional[TextDataset] = None,
        batch_size: int = 16,
    ):

        self.train = train
        self.val = val
        self.test = test
        self.encoder = encoder
        self.batch_size = batch_size


    def train_dataloader(self) -> DataLoader:

        return DataLoader(
            self.train,
            batch_size=self.batch_size,
            shuffle=True,
            collate_fn=self.encoder,
        )

    def val_dataloader(self) -> DataLoader:

        if not self.val:
            raise ValueError

        return DataLoader(
            self.val, batch_size=self.batch_size, collate_fn=self.encoder
        )

    def test_dataloader(self) -> DataLoader:

        if not self.test:
            raise ValueError

        return DataLoader(
            self.test, batch_size=self.batch_size, collate_fn=self.encoder
        )
