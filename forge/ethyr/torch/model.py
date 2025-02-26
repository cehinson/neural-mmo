from pdb import set_trace as T
import numpy as np
import torch
import time

from collections import defaultdict
from torch.nn.parameter import Parameter

from forge.ethyr.torch import save
from forge.ethyr.torch.optim import ManualAdam
from forge.ethyr.torch.param import setParameters, getParameters

class GradientOptimizer:
   def __init__(self, net, config):
      self.config = config
      self.net    = net

      self.opt = ManualAdam([net.parameters], 
         lr=self.config.LR, weight_decay=self.config.DECAY)

   #Grads and clip
   def step(self, gradList, logs):
      '''Clip the provided gradients and step the optimizer

      Args:
         gradList: a list of gradients
      '''
      grad = np.array(gradList)
      grad = np.mean(grad, 0)
      grad = np.clip(grad, -5, 5)

      gradAry = torch.Tensor(grad)
      self.opt.step(gradAry)

      self.net.syncParameters()

   def load(self, opt):
      self.opt.load_state_dict(opt.opt.state_dict())

class PopulationOptimizer:
   def __init__(self, model, config):
      self.config = config
      self.model  = model 

   def step(self, gradList, logs):
      lifetimes = defaultdict(list)
      for blob in logs.blobs:
         lifetimes[blob.annID].append(blob.lifetime)

      performance = {}
      for key, val in lifetimes.items():
         performance[key] = np.mean(val)

      performance = sorted(performance.items(), 
         key=lambda x: x[1], reverse=True)
      
      for idx in range(self.config.PERMPOPS):
         goodIdx, goodPerf = performance[idx]
         badIdx,  badPerf  = performance[-idx-1]

         self.permuteNet(goodIdx, badIdx)

   def permuteNet(self, goodIdx, badIdx):
      goodNet = self.model.net.net[goodIdx]
      badNet  = self.model.net.net[badIdx]

      goodParams = getParameters(goodNet)
      noise      = self.config.PERMVAL * np.random.randn(len(goodParams))
      goodParams = np.array(goodParams) + noise
      setParameters(badNet, goodParams)

class Model:
   '''Model manager class

   Convenience class wrapping saving/loading,
   model initialization, optimization, and logging.

   Args:
      ann: Model to optimize. Used to initialize weights.
      config: A Config specification
      args: Hook for additional user arguments
   '''
   def __init__(self, ann, config):
      self.saver = save.Saver(config.MODELDIR,
            'models', 'bests', resetTol=256)
      self.config = config

      print('Initializing new model...')
      self.net = ann(config)
      self.parameters = Parameter(torch.Tensor(
            np.array(getParameters(self.net))))

   def load(self, opt, best=False):
      '''Load a model from file

      Args:
         best (bool): Whether to load the best (True)
             or most recent (False) checkpoint
      '''
      print('Loading model...')
      epoch = self.saver.load(opt, self.parameters, best)
      self.syncParameters()

   def checkpoint(self, opt, reward):
      '''Save the model to checkpoint

      Args:
         reward: Mean reward of the model
      '''
      self.saver.checkpoint(self.parameters, opt, reward)
      self.saver.print()

   @property
   def nParams(self):
      '''Print the number of model parameters'''
      nParams = len(self.weights)
      print('#Params: ', str(nParams/1000), 'K')

   def syncParameters(self):
      parameters = self.parameters.detach().numpy().tolist()
      setParameters(self.net, parameters)

   @property
   def weights(self):
      '''Get model parameters

      Returns:
         a numpy array of model parameters
      '''
      return getParameters(self.net)


