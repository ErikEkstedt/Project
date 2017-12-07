# This script is heavily inspired by
# https://github.com/ikostrikov/pytorch-a2c-ppo-acktr
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable

import copy
import math


def weights_init_mlp(m):
    classname = m.__class__.__name__
    if classname.find('Linear') != -1:
        m.weight.data.normal_(0, 1)
        m.weight.data *= 1 / torch.sqrt(
            m.weight.data.pow(2).sum(1, keepdim=True))

        if m.bias is not None:
            m.bias.data.fill_(0)


def total_params(p):
    n = 1
    for i in p:
        n *= int(i)
    return n


class AddBias(nn.Module):
        ''' Custom "layer" that adds a bias. Trainable nn.Parameter '''
        def __init__(self, size):
            super(AddBias, self).__init__()
            self.size = size
            self.std = nn.Parameter(torch.zeros(size).unsqueeze(1))

        def forward(self, x):
            return x + self.std.t().view(1, -1)

        def __repr__(self):
            return self.__class__.__name__ + '(' + str(self.size) + ')'


# class DiagonalGaussian(nn.Module):
#     ''' Diagonal Gaussian used as the head of the policy networks
#     '''
#     def __init__(self, num_inputs, num_outputs, fixed_std=False, std=None):
#         super(DiagonalGaussian, self).__init__()
#         self.mean = nn.Linear(num_inputs, num_outputs)
#         self.logstd = AddBias(num_outputs)
#         weights_init_mlp(self)
#         self.train()
#
#     def forward(self, x):
#         action_mean = self.mean(x)
#         zeros = Variable(torch.zeros(action_mean.size()), volatile=x.volatile)
#         if x.is_cuda:
#             zeros = zeros.cuda()
#             action_mean = action_mean.cuda()
#
#         action_logstd = self.logstd(zeros)
#         return action_mean, action_logstd
#
#     def cuda(self, *args):
#         super(DiagonalGaussian).cuda()

class DiagonalGaussian(nn.Module):
    ''' Diagonal Gaussian used as the head of the policy networks
    '''
    def __init__(self, num_inputs, num_outputs):
        super(DiagonalGaussian, self).__init__()
        self.mean = nn.Linear(num_inputs, num_outputs)
        weights_init_mlp(self)
        self.train()

    def forward(self, x, std):
        action_mean = self.mean(x)
        zeros = Variable(torch.zeros(action_mean.size()), volatile=x.volatile)
        if x.is_cuda:
            zeros = zeros.cuda()
            action_mean = action_mean.cuda()

        action_logstd = zeros*std
        return action_mean, action_logstd

    def cuda(self, *args):
        super(DiagonalGaussian).cuda()

class MLPPolicy(nn.Module):
    ''' Todo: should be dynamic in amounts of layers'''
    def __init__(self,
                 input_size,
                 action_shape,
                 hidden=64,
                 std_start=-0.6,
                 std_stop=-1.7,
                 total_frames=1e6):
        super(MLPPolicy, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden)
        self.fc2 = nn.Linear(hidden, hidden)

        self.value = nn.Linear(hidden, 1)
        self.action = nn.Linear(hidden, action_shape)
        # self.diag_gauss = DiagonalGaussian(hidden, action_shape, std=std)
        self.train()

        self.n = 0
        self.total_n = total_frames
        self.std_start = std_start
        self.std_stop = std_stop

    def std(self, x):
        ratio = self.n/self.total_n
        self.log_std_value = self.std_start - (self.std_start - self.std_stop)*ratio
        std = torch.FloatTensor([self.log_std_value])
        ones = torch.ones(x.data.size())
        if x.is_cuda:
            std = std.cuda()
            ones=ones.cuda()
        std = std*ones
        std = Variable(std)
        return std

    def get_std(self):
        return math.exp(self.log_std_value)

    def forward(self, x):
        x = F.tanh(self.fc1(x))
        x = F.tanh(self.fc2(x))
        v = self.value(x)
        ac_mean = self.action(x)
        ac_std = self.std(ac_mean)  #std annealing
        # ac_mean, ac_std = self.diag_gauss(x, std)
        return v, ac_mean, ac_std

    def evaluate_actions(self, x, actions):
        v, action_mean, action_logstd = self(x)
        action_std = action_logstd.exp()

        # calculate `old_log_probs` directly in exploration.
        action_log_probs = -0.5 * ((actions - action_mean) / action_std).pow(2)\
            - 0.5 * math.log(2 * math.pi) - action_logstd
        action_log_probs = action_log_probs.sum(1, keepdim=True)

        dist_entropy = 0.5 + math.log(2 * math.pi) + action_log_probs
        dist_entropy = dist_entropy.sum(-1).mean()
        return v, action_log_probs, dist_entropy

    def sample(self, s_t, deterministic=False):
        input = Variable(s_t, volatile=True)
        v, action_mean, action_logstd = self(input)
        action_std = action_logstd.exp()

        if deterministic:
            action = action_mean
        else:
            # only care about noise if stochastic
            # normal dist. mean=0, std=1
            noise = Variable(torch.randn(action_std.size()))
            if action_mean.is_cuda:
                noise = noise.cuda()
                # action_std = action_std.cuda()
            # noise_scaler is for scaling the randomneww on the fly.
            # debugging exploration
            action = action_mean +  action_std * noise

        # calculate `old_log_probs` directly in exploration.
        action_log_probs = -0.5 * ((action - action_mean) / action_std).pow(2)\
            - 0.5 * math.log(2 * math.pi) - action_logstd
        action_log_probs = action_log_probs.sum(1, keepdim=True)

        dist_entropy = 0.5 + math.log(2 * math.pi) + action_log_probs
        dist_entropy = dist_entropy.sum(-1).mean()
        return v, action, action_log_probs, action_std




    # def reset_parameters(self):
    #     """
    #     tanh_gain = nn.init.calculate_gain('tanh')
    #     self.a_fc1.weight.data.mul_(tanh_gain)
    #     self.a_fc2.weight.data.mul_(tanh_gain)
    #     self.v_fc1.weight.data.mul_(tanh_gain)
    #     self.v_fc2.weight.data.mul_(tanh_gain)
    #     """
    #     self.apply(weights_init_mlp)
    #     if self.head.__class__.__name__ == "DiagonalGaussian":
    #         self.head.mean.weight.data.mul_(0.01)


class Obs_stats(object):
    ''' Not very good to do on tasks requiring data about target
    in the state data '''
    def __init__(self, num_inputs):
        self.n = torch.zeros(num_inputs)
        self.mean = torch.zeros(num_inputs)
        self.mean_diff = torch.zeros(num_inputs)
        self.var = torch.zeros(num_inputs)

    def observes(self, obs):
        # observation mean var updates
        x = obs
        self.n += 1.
        last_mean = self.mean.clone()
        self.mean += (x-self.mean)/self.n
        self.mean_diff += (x-last_mean)*(x-self.mean)
        self.var = torch.clamp(self.mean_diff/self.n, min=1e-2)

    def normalize(self, inputs):
        obs_std = self.var.sqrt()
        inputs = inputs
        return torch.clamp((inputs-self.mean)/obs_std, -5., 5.)


if __name__ == '__main__':
    import roboschool
    import gym
    import numpy as np
    from arguments import FakeArgs

    args = FakeArgs()

    env_id = 'RoboschoolReacher-v1'
    env = gym.make(env_id)

    ob_shape = env.observation_space.shape[0]
    ac_shape = env.action_space.shape[0]

    # obs_stats = Shared_obs_stats(ob_shape)
    obs_stats = Obs_stats(ob_shape)

    pi = MLPPolicy(ob_shape, ac_shape, hidden=64)
    print(pi)

    s = env.reset()
    s = torch.from_numpy(s).float()
    for i in range(100):
        print('s: ', s)
        # obs_stats.observes(s)
        # s = obs_stats.normalize(s)
        # print('s_norm: ',s)
        input()
        v, ac, ac_log_probs, ac_std = pi.sample(s)
        print(ac)

        s, r, done, _ = env.step(ac[0].data.numpy())
        s = torch.from_numpy(s).float()
        print(r)
