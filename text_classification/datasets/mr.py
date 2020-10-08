import os
from functools import partial
from typing import Callable, Optional, Union

from .base import DATASETS, TextDataset
from ..utils.datasets import (
    get_data_from_file,
    map_list_to_example,
    parse_line_without_label,
)
from ..tokenizers import SimpleTokenizer, SpacyTokenizer, BaseTokenizer
from ..utils import download_extract


def MRDataset(
    root: str = ".data",
    name: str = "mr",
    tokenizer: Union[Callable, str] = "spacy",
    filter_func: Optional[Callable] = None,
):

    r"""
    Load the Movie Reviews (MR) Dataset

    Function to load data, tokenize and filter examples.

    Source: `Movie Review Data <https://www.cs.cornell.edu/people/pabo/movie-review-data/>`_

    Args:
        root: Name of the root directory in which to store data.
        name: Name of the folder within root directory to store data.
        tokenizer: Tokenizer function to tokenize strings into a list of tokens. Option between
            "spacy" and "simple" to use a SpaCy and white-space tokenizer respectively.
            Custom tokenizer can be used by passing a callable.
        filter_func: Function used to filter out examples. At the stage of filtering,
            each example is represented by a dataclass with two attributes: text and label

    Returns:
        Processed dataset

    Example::

        >>> mr_data = MRDataset()
        # get only positive examples
        >>> pos_examples = MRDataset(filter_func = lambda x: x.label == 'positive')

    """

    dir_name = "rt-polaritydata"

    if tokenizer == "spacy":
        tok = SpacyTokenizer()
    elif tokenizer == "simple":
        tok = SimpleTokenizer()
    else:
        assert isinstance(tokenizer, BaseTokenizer)
        tok = tokenizer

    # download and extract dataset
    url = DATASETS["mr"]
    download_extract(url, name, root=root)

    # define a parser to format each example - use partial to supply additional
    # arguments
    pos_parser = partial(parse_line_without_label, label="positive")
    neg_parser = partial(parse_line_without_label, label="negative")

    # get data from all files using defined parser
    pos = get_data_from_file(
        os.path.join(root, name, dir_name, "rt-polarity.pos"), pos_parser
    )
    neg = get_data_from_file(
        os.path.join(root, name, dir_name, "rt-polarity.neg"), neg_parser
    )

    all_examples = pos + neg

    # data: List of lists. Using map function to filter, tokenize and convert to list of Examples
    map_f = partial(
        map_list_to_example,
        tokenizer=tok,
        filter_func=filter_func,
        label_map=None,
    )

    # define attributes of the dataset. Can be passed to TextDataset instance.
    attributes = {
        "name": name,
        "tokenizer": tok.__str__() if isinstance(tok, BaseTokenizer) else None,
    }

    return (
        TextDataset([x for x in map(map_f, all_examples) if x], attributes=attributes),
    )