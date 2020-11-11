from typing import List, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch.nn.parameter import Parameter

class PositionwiseFeedforwardLayer(nn.Module):
    def __init__(self, hid_dim, pf_dim, dropout):
        super().__init__()
        
        self.fc_1 = nn.Linear(hid_dim, pf_dim)
        self.fc_2 = nn.Linear(pf_dim, hid_dim)
        
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x):
        
        #x = [batch size, seq len, hid dim]
        
        x = self.dropout(torch.relu(self.fc_1(x)))
        
        #x = [batch size, seq len, pf dim]
        
        x = self.fc_2(x)
        
        #x = [batch size, seq len, hid dim]
        
        return x

class ScaledDotProductAttention(nn.Module):

    def __init__(self, scale, dropout):
        super().__init__()

        self.dropout = nn.Dropout(dropout)

        self.register_buffer('scale', scale)

    def forward(self, q, k, v, mask=None):

        energy = torch.einsum('...ij,...kj->...ik', [q, k]) / self.scale

        if mask is not None:
            energy = energy.masked_fill(mask == 0, -1e10)
        
        attention = self.dropout(torch.softmax(energy, dim = -1))
        output = torch.einsum('...qk,...kd->...qd', [attention, v]) 

        return output, attention



class MultiHeadAttentionLayer(nn.Module):
    def __init__(self, hid_dim, num_heads, dropout):
        super().__init__()

        assert hid_dim % num_heads == 0
        
        self.hid_dim = hid_dim
        self.num_heads = num_heads
        self.head_dim = hid_dim // num_heads
        
        self.q_proj_weight = Parameter(torch.Tensor(hid_dim, hid_dim)) # W_i^Q
        self.k_proj_weight = Parameter(torch.Tensor(hid_dim, hid_dim)) # W_i^K
        self.v_proj_weight = Parameter(torch.Tensor(hid_dim, hid_dim)) # W_i^V
        self.out_proj = Parameter(torch.Tensor(hid_dim, hid_dim)) # W^0

        scale = torch.sqrt(torch.FloatTensor([self.head_dim]))
        self.attention = ScaledDotProductAttention(scale, dropout)
        
    def forward(self, query, key, value, mask = None):
        
        batch_size = query.shape[0]
        
        q = torch.einsum('...ij,jk->...ik', [query, self.q_proj_weight]) #QW_i^Q 
        k = torch.einsum('...ij,jk->...ik', [key, self.k_proj_weight]) #KW_i^K
        v = torch.einsum('...ij,jk->...ik', [value, self.v_proj_weight]) #VW_i^V

        q_split = q.view(batch_size, -1, self.num_heads, self.head_dim).permute(0,2,1,3)
        k_split = k.view(batch_size, -1, self.num_heads, self.head_dim).permute(0,2,1,3)
        v_split = v.view(batch_size, -1, self.num_heads, self.head_dim).permute(0,2,1,3)
        
        output, attention = self.attention(q_split, k_split, v_split, mask)
        
        x = output.permute(0, 2, 1, 3).contiguous()
        
        x = x.view(batch_size, -1, self.hid_dim)
        
        x = torch.einsum('...ij,jk->...ik', [x, self.out_proj])
                
        return x, attention

class EncoderLayer(nn.Module):

    def __init__(
        self, 
        hid_dim: int,
        num_heads: int,
        pf_dim: int,
        dropout: float
    ):
        super().__init__()

        self.attn_layer_norm = nn.LayerNorm(hid_dim)
        self.ff_layer_norm = nn.LayerNorm(hid_dim)
        self.attn = MultiHeadAttentionLayer(hid_dim, num_heads, dropout)
        self.positionwise_feedforward = PositionwiseFeedforwardLayer(hid_dim, pf_dim, dropout)

        self.dropout = nn.Dropout(dropout)

    def forward(self, src, src_mask):

        _src, _ = self.attn(src, src, src, src_mask)

        # dropout, residual connection and layer norm
        src = self.attn_layer_norm(src + self.dropout(_src))

        # position-wise feedforward
        _src = self.positionwise_feedforward(src)

        # dropout, residual connection and layer norm
        src = self.ff_layer_norm(src + self.dropout(_src))

        return src

class Transformer(nn.Module):
    def __init__(
        self, 
        input_size: int, 
        num_class: int,
        hid_dim: int = 512, 
        n_layers: int = 6, 
        n_heads: int = 8, 
        pf_dim: int = 1024,
        dropout: float = 0.1,
        mlp_dim: int = 256, 
        padding_idx: int = 0,
        max_length: int = 284
    ):
        super().__init__()
        
        self.tok_embedding = nn.Embedding(input_size, hid_dim, padding_idx=padding_idx)
        self.pos_embedding = nn.Embedding(max_length, hid_dim)
        
        self.layers = nn.ModuleList([EncoderLayer(hid_dim, 
                                                  n_heads, 
                                                  pf_dim,
                                                  dropout) 
                                     for _ in range(n_layers)])
        
        self.dropout = nn.Dropout(dropout)

        self.register_buffer('scale', torch.sqrt(torch.FloatTensor([hid_dim])))

        self.fc = nn.Sequential(
            nn.Linear(hid_dim, mlp_dim),
            nn.ReLU(),
            self.dropout,
            nn.Linear(mlp_dim, num_class),
        )

    def make_src_mask(self, src):
        
        #src = [batch size, src len]
        
        src_mask = (src != 0).unsqueeze(1).unsqueeze(2)

        #src_mask = [batch size, 1, 1, src len]

        return src_mask
    
        
    def forward(self, batch):
        
        #src = [batch size, src len]
        #src_mask = [batch size, src len]

        src, _ = batch

        src_mask = self.make_src_mask(src)
        
        batch_size, src_len = src.shape
        
        pos = torch.arange(0, src_len, device=src.device).unsqueeze(0).repeat(batch_size, 1)
        
        #pos = [batch size, src len]
        
        src = self.dropout((self.tok_embedding(src) * self.scale) + self.pos_embedding(pos))
        
        #src = [batch size, src len, hid dim]
        
        for layer in self.layers:
            src = layer(src, src_mask)
            
        #src = [batch size, src len, hid dim]
        out = self.fc(src[:, 0, :])
        return out