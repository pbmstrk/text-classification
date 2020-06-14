import torch.nn as nn
import numpy as np
from abc import abstractmethod
import torch

class BaseModel(nn.Module):
    """
    Base class for all models
    """

    @abstractmethod
    def forward(self, *inputs):
        """
        Forward pass logic
        :return: Model output
        """
        raise NotImplementedError

    def __str__(self):
        
        """
        Model prints with number of trainable parameters
        """

        model_parameters = filter(lambda p: p.requires_grad, self.parameters())
        params = sum([np.prod(p.size()) for p in model_parameters])
        return super().__str__() + '\nTrainable parameters: {}'.format(params)

    def save(self, path):

        torch.save(self.state_dict(), path)

    def load(self, path):

        self.load_state_dict(torch.load(path))