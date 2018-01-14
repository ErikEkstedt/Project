'''
Main
'''

import os
import numpy as np
import torch
import torch.optim as optim

from utils.utils import make_log_dirs
from utils.arguments import get_args
from utils.vislogger import VisLogger
from models.combine import CombinePolicy

from agent.test import Test_and_Save_Video_Combi as Test_and_Save_Video
from agent.train import explorationSocial as exploration
from agent.train import trainSocial as train
from agent.memory import RolloutStorageCombi as RolloutStorage
from agent.memory import Results, Current, Targets
from agent.memory import StackedObs, StackedState
from environments.social import Social, Social_multiple


def print_shapes(s, obs, CurrentState, CurrentStateTarget, CurrentObs, CurrentObsTarget):
    '''print all the shapes'''
    print('-' * 80)
    print('s.shape', s.shape)
    print('s_target.shape', s.shape)
    print()
    print('type(obs)', type(obs))
    print('obs.shape', obs.shape)
    print('obs.mean', obs.mean())
    print()
    print('CurrentObs().size()', CurrentObs().size())
    print('CurrentObs().mean()', CurrentObs().mean())
    print()
    print('CurrentObsTarget().size()', CurrentObsTarget().size())
    print('CurrentObsTarget().mean()', CurrentObsTarget().mean())
    print()
    print('CurrentState().size()', CurrentState().size())
    print('CurrentState().mean()', CurrentState().mean())
    print('CurrentStateTarget().size()', CurrentStateTarget().size())
    print('CurrentStateTarget().mean()', CurrentStateTarget().mean())
    input('Press Enter to continue')

def main():
    args = get_args()
    print('Social')

    # === Targets ===
    print('Loading target labels...')
    train_dset = torch.load(args.target_path)
    test_dset = torch.load(args.target_path2)

    s_target, o_target = train_dset[4]  # choose random data point
    s_te, o_te = test_dset[4]  # check to have same dims as training set
    assert s_target.shape == s_te.shape, 'training and test shapes do not match'
    assert o_target.shape == o_te.shape, 'training and test shapes do not match'

    # Force Settings
    args.video_w = o_target.shape[0]  # (W,H,C)
    args.video_h = o_target.shape[1]

    if args.verbose:
        print('ob shape: {}, st_shape: {}, COMBI: {}'.format(
            o_target.shape, s_target.shape, args.COMBI))
        print('args- Video_W: {}, Video_H: {}'.format(args.video_w, args.video_h))
        input('Press Enter to continue')

    targets = Targets(n=args.num_processes, dset=train_dset)
    # frames -> updates
    args.num_updates = int(args.num_frames) // args.num_steps // args.num_processes
    args.test_thresh = int(args.test_thresh) // args.num_steps // args.num_processes

    make_log_dirs(args)
    if not args.no_vis:
        vis = VisLogger(args)

    # === Environment ===
    Env = Social  # using Env as variable so I only need to change this line between experiments

    # trainWarning
    env = Social_multiple(args)

    s_target_shape = s_target.shape[0]
    s_shape = env.state_space.shape[0]    # Joints state
    ob_shape = env.observation_space.shape  # RGB
    ac_shape = env.action_space.shape[0]   # Actions

    # test environment
    test_env = Env(args)
    test_env.seed(np.random.randint(0, 20000))

    # === Memory ===
    result = Results(200, 10)
    current = Current(args, s_shape, s_target_shape, ob_shape, ob_shape)
    rollouts = RolloutStorage(args.num_steps,
                              args.num_processes,
                              current.state.size()[1],
                              current.target_state.size()[1],
                              current.obs.size()[1:],
                              ac_shape)

    # === Model ===
    pi = CombinePolicy(o_shape=current.obs.obs_shape,
                       o_target_shape=current.obs.obs_shape,
                       s_shape=s_shape,
                       s_target_shape=s_target_shape,
                       a_shape=ac_shape,
                       feature_maps=[64, 64, 8],
                       kernel_sizes=[5, 5, 5],
                       strides=[2, 2, 2],
                       args=args)

    optimizer_pi = optim.Adam(pi.parameters(), lr=args.pi_lr)
    print('Environment', args.env_id)
    print('Actions:', ac_shape)
    print('State:', s_shape)
    print('State target:', s_target_shape)
    print('Obs:', ob_shape)
    print('Obs target:', ob_shape)
    print('\nPOLICY:\n', pi)
    print('Total network parameters to train: ', pi.total_parameters())


    print('\nTraining for %d Updates' % args.num_updates)

    # ==== Training ====

    # init_target = [train_dset[0]] * args.num_processes
    env.set_target(targets())

    s, s_target, obs, obs_target = env.reset()
    current.update(s, s_target, obs, obs_target)

    rollouts.states[0].copy_(current.state())
    rollouts.observations[0].copy_(current.obs())
    rollouts.target_states[0].copy_(current.target_state())
    rollouts.target_observations[0].copy_(current.target_obs())

    if args.cuda:
        current.cuda()
        rollouts.cuda()
        pi.cuda()

    pi.train()

    MAX_REWARD = -99999
    for j in range(args.num_updates):
        exploration(pi, current, targets, rollouts, args, result, env)
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
        # if not args.no_test and j % args.test_interval < nt:
        if not args.no_test and j % args.test_interval < nt and j > args.test_thresh:
            if j % args.test_interval == 0:
                print('-'*45)
                print('Testing {} episodes'.format(args.num_test))

            pi.cpu()
            sd = pi.cpu().state_dict()
            test_reward_list, bestvideo = Test_and_Save_Video(test_env, test_dset, CombinePolicy, sd, args)

            test_reward_list = np.array(test_reward_list)
            test_reward = test_reward_list.mean()

            result.update_test(test_reward_list)

            # Plot result
            print('Average Test Reward: {}\n '.format(round(test_reward)))
            if args.vis:
                vis.line_update(Xdata=frame,
                                Ydata=test_reward, name='Test Score')
                # vis.scatter_update(Xdata=frame,
                #                 Ydata=test_reward, name='Test Score Scatter')
            #  ==== Save best model ======
            if test_reward > MAX_REWARD:
                print('--' * 45)
                print('New High Score!\n')
                print('Avg. Reward: ', test_reward)
                name = os.path.join(args.result_dir,
                    'BestVideo_targets{}_{}.pt'.format(round(test_reward, 1), frame))
                print('Saving Best Video')
                torch.save(bestvideo, name)
                name = os.path.join(
                    args.checkpoint_dir,
                    'BestDictCombi{}_{}.pt'.format(frame, round(test_reward, 3)))
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