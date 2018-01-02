import numpy as np
import gym
from copy import deepcopy
import os

import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.optim as optim

from .utils import log_print, make_log_dirs
from .arguments import FakeArgs, get_args
from .model import MLPPolicy
from .memory import RolloutStorage, StackedState, Results

from .train import train, exploration
from .test import test, test_existing_env, Test_and_Save_Video, test_and_render

from .utils import get_env
from project.environments.Reacher import ReacherPlane


def main():
    args = get_args()

    # === Environment ===
    Env = get_env(args)

    # Logger
    make_log_dirs(args)

    args.num_updates   = int(args.num_frames) // args.num_steps // args.num_processes

    if args.vis:
        from vislogger import VisLogger
        vis = VisLogger(args)

    if args.num_processes > 1:
        from train import exploration
        env = make_parallel_environments(Env,args)
    else:
        from train import Exploration_single as exploration
        env = Env(args)
        env.seed(args.seed)

    tmp_rgb = args.RGB # save rgb flag
    if args.video:
        args.RGB = True
        video_env = Env(args)

    args.RGB = True
    test_env = Env(args)
    args.RGB = tmp_rgb # reset rgb flag

    ob_shape = env.observation_space.shape[0]
    ac_shape = env.action_space.shape[0]
        # === Memory ===
    result = Results(max_n=200, max_u=10)
    CurrentState = StackedState(args.num_processes,
                                args.num_stack,
                                ob_shape)

    rollouts = RolloutStorage(args.num_steps,
                              args.num_processes,
                              CurrentState.size()[1],
                              ac_shape)

    # === Model ===
    pi = MLPPolicy(CurrentState.state_shape,
                   ac_shape,
                   hidden=args.hidden,
                   total_frames=args.num_frames)

    pi.train()
    optimizer_pi = optim.Adam(pi.parameters(), lr=args.pi_lr)

    # ==== Training ====
    print('Learning {}(ac: {}, ob: {})'.format( args.env_id, ac_shape, ob_shape))
    print('\nTraining for %d Updates' % args.num_updates)
    s = env.reset()
    CurrentState.update(s)
    rollouts.states[0].copy_(CurrentState())

    if args.cuda:
        CurrentState.cuda()
        rollouts.cuda()
        pi.cuda()

    MAX_REWARD = -999999
    for j in range(args.num_updates):
        exploration(pi, CurrentState, rollouts, args, result, env)
        vloss, ploss, ent = train(pi, args, rollouts, optimizer_pi)

        rollouts.last_to_first()
        result.update_loss(vloss.data, ploss.data, ent.data)
        frame = pi.n * args.num_processes

        #  ==== SHELL LOG ======
        if j % args.log_interval == 0 and j > 0:
            result.plot_console(frame)

        #  ==== VISDOM PLOT ======
        if j % args.vis_interval == 0 and j > 0 and not args.no_vis:
            result.vis_plot(vis, frame, pi.get_std())

        #  ==== TEST ======
        nt = 5
        if not args.no_test and j % args.test_interval < nt:
            ''' `j % args.test_interval < 5` is there because:
            If tests are not performed during some interval bad luck might make
            it that although the model becomes better the test occured
            during a bad policy update. The policy adjust for this in the next
            update but we might miss good policies if we test too seldom.
            Thus we test in an interval of 5 every args.test_interval.
            (default: args.num_test = 50)
                -> test updates [50,54], [100,104], ...
            '''
            if j % args.test_interval == 0:
                print('-'*45)
                print('Testing {} episodes'.format(args.num_test))

            pi.cpu()
            sd = deepcopy(pi.cpu().state_dict())
            # test_reward = test(test_env, MLPPolicy, sd, args)
            # test_reward = test_existing_env(test_env, MLPPolicy, sd, args)
            test_reward, BestVideo = Test_and_Save_Video(test_env, MLPPolicy, sd, args)
            # Plot result
            print('Average Test Reward: {}\n '.format(round(test_reward)))
            if args.vis:
                vis.line_update(Xdata=frame,
                                Ydata=test_reward, name='Test Score')

            #  ==== Save best model ======
            if test_reward > MAX_REWARD:
                print('--'*45)
                print('New High Score!\n')
                print('error: ', test_reward)
                name = os.path.join(args.result_dir,
                    'BESTVIDEO{}_{}.pt'.format(round(test_reward, 1), frame))
                print('Saving Best Video')
                torch.save(BestVideo, name)
                name = os.path.join(
                    args.checkpoint_dir,
                    'BESTDICT{}_{}.pt'.format(frame, round(test_reward, 3)))
                torch.save(sd, name)
                MAX_REWARD = test_reward
            else:
                name = os.path.join(
                    args.checkpoint_dir,
                    'dict_{}_TEST_{}.pt'.format(frame, round(test_reward, 3)))
                torch.save(sd, name)

            if args.cuda:
                pi.cuda()


if __name__ == '__main__':
    main()