import os
from functools import partial
from typing import Callable, Optional, Union

from .base import DATASETS, TextDataset
from ..utils.datasets import (
    get_data_from_file,
    map_list_to_example,
    parse_line_tree,
)
from ..tokenizers import SimpleTokenizer, SpacyTokenizer, BaseTokenizer
from ..utils import download_extract


def SSTDataset(
    root: str = ".data",
    name: str = "sst",
    train_subtrees: bool = False,
    fine_grained: bool = False,
    tokenizer: Union[Callable, str] = "spacy",
    filter_func: Optional[Callable] = None,
):

    r"""
    Load the Stanford Sentiment Treebank (SST) Dataset

    Function to load train, validation and test subsets, tokenize
    and filter examples.

    Source:  `SST <https://nlp.stanford.edu/sentiment/index.html>`_

    Args:
        root: Name of the root directory in which to store data.
        name: Name of the folder within root directory to store data.
        train_subtrees: Include all subtrees in training set.
        fine_grained: Use fine-grained classification (5 classes).
        tokenizer: Tokenizer function to tokenize strings into a list of tokens. Option between
            "spacy" and "simple" to use a SpaCy and white-space tokenizer respectively.
            Custom tokenizer can be used by passing a callable.
        filter_func: Function used to filter out examples. At the stage of filtering,
            each example is represented by a dataclass with two attributes: text and label

    Returns:
        Processed train, val and test datasets

    Example::

        # To include subtrees in training set
        >>> train, val, test = SSTDataset(train_subtrees='true')
        # To remove all neutral examples
        >>> train, val, test = SSTDataset(filter_func=lambda x: x.label != 'neutral')
    """

    dir_name = "trees"

    if tokenizer == "spacy":
        tok = SpacyTokenizer()
    elif tokenizer == "simple":
        tok = SimpleTokenizer()
    else:
        assert isinstance(tokenizer, BaseTokenizer)
        tok = tokenizer

    # adapted from https://github.com/pytorch/text/blob/master/torchtext/datasets/sst.py#L34-L36
    prefix = "very " if fine_grained else ""
    label_map = {
        "0": prefix + "negative",
        "1": "negative",
        "2": "neutral",
        "3": "positive",
        "4": prefix + "positive",
    }

    # download and extract dataset
    url = DATASETS["sst"]
    download_extract(url, name, root=root)

    # define a parser to format each example - use partial to supply additional
    # arguments
    parser = partial(parse_line_tree, subtrees=train_subtrees)

    # get data from all files using defined parser
    train = get_data_from_file(os.path.join(root, name, dir_name, "train.txt"), parser)
    val = get_data_from_file(os.path.join(root, name, dir_name, "dev.txt"), parser)
    test = get_data_from_file(os.path.join(root, name, dir_name, "test.txt"), parser)

    # data: List of lists. Using map function to filter, tokenize and convert to list of Examples
    map_f = partial(
        map_list_to_example,
        tokenizer=tok,
        filter_func=filter_func,
        label_map=label_map,
    )

    # define attributes of the dataset. Can be passed to TextDataset instance.
    attributes = {
        "name": name,
        "train_subtrees": train_subtrees,
        "fine_grained": fine_grained,
        "tokenizer": tok.__str__() if isinstance(tok, BaseTokenizer) else None,
    }

    return (
        TextDataset([x for x in map(map_f, train) if x], attributes=attributes),
        TextDataset([x for x in map(map_f, val) if x], attributes=attributes),
        TextDataset([x for x in map(map_f, test) if x], attributes=attributes),
    )