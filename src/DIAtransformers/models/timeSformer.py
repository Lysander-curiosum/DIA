# an implementation of the timeSformer model

from torch import nn, tensor
import torch
import numpy as np
from einops import rearrange, repeat
from einops.layers.torch import Rearrange
import math
from .utils import dividedSpaceTimeAttention

class EncoderBlock(nn.Module):
    def __init__(self, num_heads, dim, n, num_frames):
        super(EncoderBlock, self).__init__()
        # number of attention heads
        self.num_heads = num_heads
        # number of attention blocks
        self.dim = int(dim)
        self.num_frames = num_frames
        # layer normalization, to stabilize the gradients
        # should not depend on batch size
        self.n = int(n)
        #self.norm = nn.LayerNorm(normalized_shape = (self.n, self.dim))
        self.norm = nn.LayerNorm(normalized_shape = (self.num_frames * self.n + 1, dim), elementwise_affine = True)
        self.attention = dividedSpaceTimeAttention(self.num_heads, dim, self.n, num_frames)
        self.dh = int(self.dim / self.num_heads)
        self.mlp = nn.Linear(dim, dim)

        
    def forward(self, input):
        #whoa = self.norm(input)
        uhOh = self.attention.forward(input)
        uhHuh = self.norm(uhOh + input)
        toAdd = uhOh + input    
        output = self.mlp(uhHuh)
        output += toAdd
        return output


# You should be able to feed an input of any batch size to the model
class timeSformer(nn.Module):

    def __init__(self, height, width, num_frames, patch_res, dim, num_classes, batch_size):
        super(timeSformer, self).__init__()
        self.checkPass = True
        self.height = height
        self.width = width
        self.channels = 3
        self.num_classes = num_classes
        self.patch_res = patch_res 
        self.dim = int(dim)
        self.patch_dim = self.channels * patch_res * patch_res
        self.n = int((height * width) / (patch_res ** 2))


        self.patchEmbed = nn.Sequential(
            Rearrange('b f c (h p1) (w p2) -> b (f h w) (p1 p2 c)', p1 = patch_res, p2 = patch_res),
            nn.Linear(self.patch_dim, dim),)
        # the class token serves as a representation of the entire sequence
        # should attend to the entire sequence (so, it actually doesn't need to be stored with 
        # the other vectors? as long as it is weighted sum?)
        self.classtkn = nn.Parameter(torch.randn(batch_size, 1, dim))
        # this will be concated to the end of the input before positional embedding
        # should the class token be randomonly initialized? or the same across batches? See what happens during training

        # the positional embedding should be applied based on what 
        self.pos_embed = nn.Parameter(torch.randn(batch_size, num_frames * (self.n) + 1, dim))
        self.encoderBlocks = nn.ModuleList([EncoderBlock(num_heads = 8, dim = dim, n = self.n, num_frames=num_frames) for i in range(8)])

        
        self.mlpHead = nn.Sequential(nn.LayerNorm(dim), nn.GELU(), nn.Linear(self.dim, num_classes))
        self.dropout = nn.Dropout(0.1)


            

    def forward(self, vid):
        input = self.patchEmbed(vid)
        input = torch.cat((self.classtkn, input), dim = 1)
        input += self.pos_embed
        input = self.dropout(input)
        for encoder in self.encoderBlocks:
            output = encoder.forward(input)
            input = output
        out = self.mlpHead(output[:, 0])
        return out



