import torch
import torch.optim
import torch.nn
import torchnet.meter as meter
import torchnet.dataset as dataset
from torchnet.engine import Engine
from torch.utils.data import DataLoader
from torch.utils.serialization.read_lua_file import load_lua
from torch.autograd import Variable
import functional as F
import math

# mnist = require 'mnist'
# torch.save('./example/mnist.t7',{train = mnist.traindataset(), test = mnist.testdataset()})
mnist = load_lua('./example/mnist.t7')

train_ds = TensorDataset({
    'input': mnist.train.data,
    'target': mnist.train.label,
    })
train_ds = BatchDataset(train_ds, 128)
train_ds = ProgressBarDataset(train_ds)

test_ds = TensorDataset({
    'input': mnist.test.data,
    'target': mnist.test.label,
    })
test_ds = BatchDataset(test_ds, 128)
test_ds = ProgressBarDataset(test_ds)

conv_init = lambda ni, no, k: torch.Tensor(no, ni, k, k).normal_(0,2/math.sqrt(ni*k*k))
linear_init = lambda ni, no: torch.Tensor(no, ni).normal_(0,2/math.sqrt(ni))

params = {
        'conv0.weight': conv_init(1, 50, 5),
        'conv0.bias': torch.zeros(50),
        'conv1.weight': conv_init(50, 50, 5),
        'conv1.bias': torch.zeros(50),
        'linear2.weight': linear_init(800, 512),
        'linear2.bias': torch.zeros(512),
        'linear3.weight': linear_init(512, 10),
        'linear3.bias': torch.zeros(10),
        }

for k,v in params.items():
    params[k] = Variable(v, requires_grad = True)

def f(params, inputs, mode):
    o = inputs.view(inputs.size(0), 1, 28, 28)
    o = F.conv2d(o, params['conv0.weight'], stride=2, bias=params['conv0.bias'])
    o = F.relu(o)
    o = F.conv2d(o, params['conv1.weight'], stride=2, bias=params['conv1.bias'])
    o = F.relu(o)
    o = o.view(o.size(0), -1)
    o = F.dropout(o, p=0.5, train=mode)
    o = F.linear(o, params['linear2.weight'], params['linear2.bias'])
    o = F.relu(o)
    o = F.dropout(o, p=0.5, train=mode)
    o = F.linear(o, params['linear3.weight'], params['linear3.bias'])
    return o

def h(sample):
    inputs = Variable(sample['input'].float() / 255.0)
    targets = Variable(torch.LongTensor(sample['target']))
    o = f(params, inputs, sample['mode'])
    return F.cross_entropy(o, targets), o

meter_loss = AverageValueMeter()
classerr = ClassErrorMeter(accuracy=True)

def onSample(state):
    state['sample']['mode'] = state['train']

def onForward(state):
    classerr.add(state['output'].data, torch.LongTensor(state['sample']['target']))
    meter_loss.add(state['loss'].data[0])

def onStartEpoch(state):
    classerr.reset()

def onEndEpoch(state):
    print classerr.value()

optimizer = torch.optim.SGD(params.values(), lr = 0.01, momentum = 0.9, weight_decay = 0.0005)

engine = Engine()
engine.hooks['onSample'] = onSample
engine.hooks['onForward'] = onForward
engine.hooks['onStartEpoch'] = onStartEpoch
engine.hooks['onEndEpoch'] = onEndEpoch
engine.hooks['onEnd'] = onEndEpoch
engine.train(h, train_ds, 2, optimizer) 
engine.test(h, test_ds)