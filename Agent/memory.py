import torch
import numpy as np
from torch.utils.data.sampler import BatchSampler, SubsetRandomSampler
import time

class Results_single(object):
    def __init__(self, max_n=200, max_u=200):
        self.episode_rewards = 0
        self.final_reward_list = []
        self.n = 0
        self.max_n = max_n

        self.vloss = []
        self.ploss = []
        self.ent = []
        self.updates = 0
        self.max_u = max_u

    def update_list(self, idx):
        self.final_reward_list.insert(0, self.episode_rewards)
        self.episode_rewards = 0
        self.n += 1
        if self.n > self.max_n:
            self.final_reward_list.pop()

    def update_loss(self, v, p, e):
        self.vloss.insert(0, v)
        self.ploss.insert(0, p)
        self.ent.insert(0, e)
        self.updates += 1
        if self.updates > self.max_u:
            self.vloss.pop()
            self.ploss.pop()
            self.ent.pop()

    def get_reward_mean(self):
        return torch.stack(self.final_reward_list).mean()

    def get_last_reward(self):
        return self.final_reward_list[0]

    def get_loss_mean(self):
        v = torch.stack(self.vloss).mean()
        p = torch.stack(self.ploss).mean()
        e = torch.stack(self.ent).mean()
        return v, p, e

    def plot_console(self, frame):
        v, p, e = self.get_loss_mean()
        r = self.get_reward_mean()
        print('Steps: {}, Avg.Rew: {}, VLoss: {}, \
              PLoss: {},  Ent: {}'.format(frame, r, v, p, e))

    def vis_plot(self, vis, frame, std):
        training_reward_mean = self.get_reward_mean()
        v, p, e = self.get_loss_mean()

        # Draw plots
        vis.line_update(Xdata=frame, Ydata=training_reward_mean,
                        name='Training Score')
        vis.line_update(Xdata=frame, Ydata=v, name='Value Loss')
        vis.line_update(Xdata=frame, Ydata=p, name='Policy Loss')
        vis.line_update(Xdata=frame, Ydata=std, name='Action std')
        vis.line_update(Xdata=frame, Ydata=-e, name='Entropy')


class Results(object):
    def __init__(self, max_n=200, max_u=200):
        self.episode_rewards = 0
        self.tmp_final_rewards = 0
        self.final_reward_list = []
        self.n = 0
        self.max_n = max_n

        self.vloss = []
        self.ploss = []
        self.ent = []
        self.updates = 0
        self.max_u = max_u
        self.start_time = time.time()

    def time(self):
        return time.time() - self.start_time

    def update_list(self):
        self.final_reward_list.insert(0, self.tmp_final_rewards.mean())
        self.n += 1
        if self.n > self.max_n:
            self.final_reward_list.pop()

    def update_loss(self, v, p, e):
        self.vloss.insert(0, v)
        self.ploss.insert(0, p)
        self.ent.insert(0, e)
        self.updates += 1
        if self.updates > self.max_u:
            self.vloss.pop()
            self.ploss.pop()
            self.ent.pop()

    def get_reward_mean(self):
        return torch.Tensor(self.final_reward_list).mean()

    def get_last_reward(self):
        return self.final_reward_list[0]

    def get_loss_mean(self):
        v = torch.stack(self.vloss).mean()
        p = torch.stack(self.ploss).mean()
        e = torch.stack(self.ent).mean()
        return v, p, e

    def plot_console(self, frame):
        v, p, e = self.get_loss_mean()
        v, p, e = round(v, 2), round(p,2), round(e,2),
        r       = round(self.get_reward_mean(), 2)
        print('Time: {}, Steps: {}, Avg.Rew: {}, VLoss: {}, PLoss: {},  Ent: {}'.format(
            int(self.time()), frame, r, v, p, e))

    def vis_plot(self, vis, frame, std):
        tr_rew_mean = self.get_reward_mean()
        v, p, e = self.get_loss_mean()

        # Draw plots
        vis.line_update(Xdata=frame, Ydata=tr_rew_mean, name='Training Score')
        vis.line_update(Xdata=frame, Ydata=v, name='Value Loss')
        vis.line_update(Xdata=frame, Ydata=p, name='Policy Loss')
        vis.line_update(Xdata=frame, Ydata=std, name='Action std')
        vis.line_update(Xdata=frame, Ydata=-e, name='Entropy')


class StackedObs(object):
    ''' stacked obs for Roboschool

    state: np.array, shape: (num_proc, W, H, 3) (roboschoolhumanoid)

    Thus with defaults:
    current_state.size: (num_proc, 4, 44)

    update: push out the oldest 44 numbers for all procs.
    call:   return current_state.view(4,-1), concat stacked states for each proc.

    :param state_shape      int/tuple shape
    :param num_stack        int
    :param num_proc         int
    :param use_cuda         bool
    '''
    def __init__(self, num_processes=4, num_stack=1, obs_shape=(100,100,3), use_cuda=False):
        self.current_state = torch.zeros(num_processes, num_stack, *obs_shape)

        self.num_stack = num_stack
        self.obs_shape = (num_stack, *obs_shape)
        self.num_processes = num_processes
        self.use_cuda = use_cuda
        if use_cuda:
            self.cuda()

    def update(self, s):
        if type(s) is np.ndarray:
            s = torch.from_numpy(s).float()
        assert type(s) is torch.Tensor
        if self.use_cuda:
            s = s.cuda()
        if self.num_stack > 1:
            self.current_state[:,:-1,:] = self.current_state[:,1:,:] # push out oldest
            self.current_state[:,-1,:] = s  # add in newest
        else:
            self.current_state = s

    def check_and_reset(self, mask):
        '''
        :param mask     torch.Tensor, size: (num_proc, 1), and contains 1 or 0.

        If an element is zero it means that the env for that processor is `done`
        and thus we need to reset the state.
        '''
        tmp = self.current_state.view(self.num_processes, -1)
        tmp *= mask
        self.current_state = tmp.view(self.num_processes, self.num_stack, -1)

    def reset(self):
        self.current_state = torch.zeros(self.current_state.size())
        if self.use_cuda:
            self.cuda()

    def reset_to(self):
        self.current_state.copy_(state)

    def __call__(self):
        ''' Returns the flatten state (num_processes, -1)'''
        return self.current_state.view(self.num_processes, -1)

    def size(self):
        ''' Returns torch.Size '''
        return self.current_state.view(self.num_processes, -1).size()

    def cuda(self):
        self.current_state = self.current_state.cuda()
        self.use_cuda = True

    def cpu(self):
        self.state = self.state.cpu()
        self.use_cuda = False

class StackedState(object):
    ''' stacked state for Roboschool

    state: np.array, shape: (num_proc, 44) (roboschoolhumanoid)

    Thus with defaults:
    current_state.size: (num_proc, 4, 44)

    update: push out the oldest 44 numbers for all procs.
    call:   return current_state.view(4,-1), concat stacked states for each proc.

    :param state_shape      int/tuple shape
    :param num_stack        int
    :param num_proc         int
    :param use_cuda         bool
    '''
    def __init__(self, num_processes=4, num_stack=4, state_shape=44, use_cuda=False):
        if type(state_shape) is tuple:
            self.current_state = torch.zeros(num_processes, num_stack, *state_shape)
        else:
            self.current_state = torch.zeros(num_processes, num_stack, state_shape)

        self.num_stack = num_stack
        self.state_shape = state_shape * num_stack
        self.num_processes = num_processes
        self.use_cuda = use_cuda
        if use_cuda:
            self.cuda()

    def update(self, s):
        if type(s) is np.ndarray:
            s = torch.from_numpy(s).float()
        assert type(s) is torch.Tensor
        if self.use_cuda:
            s = s.cuda()
        if self.num_stack > 1:
            self.current_state[:,:-1,:] = self.current_state[:,1:,:] # push out oldest
            self.current_state[:,-1,:] = s  # add in newest
        else:
            self.current_state = s

    def check_and_reset(self, mask):
        '''
        :param mask     torch.Tensor, size: (num_proc, 1), and contains 1 or 0.

        If an element is zero it means that the env for that processor is `done`
        and thus we need to reset the state.
        '''
        tmp = self.current_state.view(self.num_processes, -1)
        tmp *= mask
        self.current_state = tmp.view(self.num_processes, self.num_stack, -1)

    def reset(self):
        self.current_state = torch.zeros(self.current_state.size())
        if self.use_cuda:
            self.cuda()

    def reset_to(self):
        self.current_state.copy_(state)

    def __call__(self):
        ''' Returns the flatten state (num_processes, -1)'''
        return self.current_state.view(self.num_processes, -1)

    def size(self):
        ''' Returns torch.Size '''
        return self.current_state.view(self.num_processes, -1).size()

    def cuda(self):
        self.current_state = self.current_state.cuda()
        self.use_cuda = True

    def cpu(self):
        self.state = self.state.cpu()
        self.use_cuda = False


# https://github.com/ikostrikov/pytorch-a2c-ppo-acktr
class RolloutStorage(object):
    ''' Usage Description
    First manually make the first state be the reset state
    from env (state[0] = env.reset).

    Then gather samples and use self.insert(step, s, a, v, r, mask).

    Then after `num_steps` samples have been gathered manually add the value
    calculated from the last state.

    example:

        RolloutStorage.states[0].copy_(s)
        for step in num_steps:
            self.insert(step, s, a, v, r, mask).
        RolloutStorage.compute_returns(next_value, *args)

    then samples batches from self.state, self.rewards,
    self.value_pred, self.returns, self.masks

    states and values has one extra data point for `next value` when computing
    returns.
    '''
    def __init__(self, num_steps, num_processes, stacked_state_shape, action_shape):
        self.states           = torch.zeros(num_steps+1, num_processes, stacked_state_shape)
        self.value_preds      = torch.zeros(num_steps+1, num_processes, 1)
        self.returns          = torch.zeros(num_steps+1, num_processes, 1)
        self.masks            = torch.ones(num_steps+1, num_processes, 1)
        self.actions          = torch.zeros(num_steps, num_processes, action_shape)
        self.action_log_probs = torch.zeros(num_steps, num_processes, 1)
        self.rewards          = torch.zeros(num_steps, num_processes, 1)
        self.num_processes    = num_processes
        self.num_steps        = num_steps

        # self.observations = torch.zeros(num_steps+1, num_processes, *stacked_state_shape)
    def cuda(self):
        self.states           = self.states.cuda()
        self.rewards          = self.rewards.cuda()
        self.value_preds      = self.value_preds.cuda()
        self.returns          = self.returns.cuda()
        self.actions          = self.actions.cuda()
        self.masks            = self.masks.cuda()
        self.action_log_probs = self.action_log_probs.cuda()

    def insert(self, step, state, action, action_log_prob, value_pred, reward, mask):
        #def insert(self, step, current_obs, state, action, action_log_prob, value_pred, reward, mask):
        # self.observations[step + 1].copy_(current_obs)
        self.states[step + 1].copy_(state)
        self.masks[step + 1].copy_(mask)
        self.actions[step].copy_(action)
        self.action_log_probs[step].copy_(action_log_prob)
        self.value_preds[step].copy_(value_pred)
        self.rewards[step].copy_(reward)

    def last_to_first(self):
        # self.observations[0].copy_(self.observations[-1])
        self.states[0].copy_(self.states[-1])
        self.masks[0].copy_(self.masks[-1])

    def get_last_state(self):
        '''
        Mostly used for calculating `next value_prediction` before training.
        use `view(num_proc, -1)` to get correct dims for policy.
        '''
        return self.states[-1].view(self.num_processes, -1)

    def compute_returns(self, next_value, no_gae, gamma, tau):
        if not no_gae:
            self.value_preds[-1] = next_value
            gae = 0
            for step in reversed(range(self.rewards.size(0))):
                delta = self.rewards[step] + gamma * self.value_preds[step + 1] * self.masks[step + 1] - self.value_preds[step]
                gae = delta + gamma * tau * self.masks[step + 1] * gae
                self.returns[step] = gae + self.value_preds[step]
        else:
            self.returns[-1] = next_value
            for step in reversed(range(self.rewards.size(0))):
                self.returns[step] = self.returns[step + 1] * \
                    gamma * self.masks[step + 1] + self.rewards[step]


    def Batch(self, advantages, mini_batch):
        '''
        Batch the data.
        Grab `indices` datapoints from states, rewards, etc...
        Reshape into correct shape such that everything migth be passed through a network
        in one forward pass.

        :param advantages       torch.Tensor
        :param mini_batch       int, size of batch (64, 128 etc)
        '''

        data_size = self.num_processes * self.num_steps  # total data size is steps*processsors

        # Choose `mini_batch` indices from total `data_size`.
        # Choose `64` indices from total `2048`.
        sampler = BatchSampler(SubsetRandomSampler(range(data_size)),
                               mini_batch, drop_last=False)

        for indices in sampler:
            indices = torch.LongTensor(indices)

            if advantages.is_cuda:
                indices = indices.cuda()

            # all but last entry
            # observations_batch = self.observations[:-1].view(-1, *self.observations.size()[2:])[indices]
            states_batch = self.states[:-1].view(-1, self.states.size(-1))[indices]
            return_batch = self.returns[:-1].view(-1, 1)[indices]
            masks_batch  = self.masks[:-1].view(-1, 1)[indices]

            # all entries
            actions_batch = self.actions.view(-1, self.actions.size(-1))[indices]
            old_action_log_probs_batch = self.action_log_probs.view(-1, 1)[indices]
            adv_targ = advantages.view(-1, 1)[indices]

            yield states_batch, actions_batch, return_batch, masks_batch, old_action_log_probs_batch, adv_targ


if __name__ == '__main__':
    from arguments import get_args
    from environments.Reacher import ReacherPlane as Env
    from environments.utils import make_parallel_environments

    args = get_args()

    s_env = Env(args)
    m_env = make_parallel_environments(Env, args)

    m_ob = m_env.observation_space.shape[0]
    m_ac = m_env.action_space.shape[0]
    print('Mult:\nob: {}\nac: {}\n'.format(m_ob, m_ac))

    s_ob = s_env.observation_space.shape[0]
    s_ac = s_env.action_space.shape[0]
    print('Single:\nob: {}\nac: {}\n'.format(s_ob, s_ac))

    # === Memory ===
    multstate = StackedState(args.num_processes, args.num_stack, m_ob)
    singlestate = StackedState(1, args.num_stack, s_ob)

    print('Num_stack:', args.num_stack)
    print('MultState:\nsize:{}\n'.format(multstate.size()))
    print('SingleState:\nsize:{}\n'.format(singlestate.size()))

    m = m_env.reset()
    multstate.update(m)

    s = s_env.reset()
    singlestate.update(s)

    print('MultState:\nCall:{}\n'.format(multstate()))
    print('SingleState:\nCall:{}\n'.format(singlestate()))

    m = m_env.reset()
    multstate.update(m)
    s = s_env.reset()
    singlestate.update(s)

    print('MultState:\nCall:{}\n'.format(multstate()))
    print('SingleState:\nCall:{}\n'.format(singlestate()))

