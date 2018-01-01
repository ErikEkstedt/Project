import gym
import numpy as np

PATH_TO_CUSTOM_XML = "/home/erik/com_sci/Master_code/Project/environments/xml_files"

class MyGymEnv(gym.Env):
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second': 60
        }

    def __init__(self, action_dim=2, obs_dim=7, RGB=False, W=600, H=400):
        self.scene = None
        self.RGB = RGB
        self.VIDEO_W = W
        self.VIDEO_H = H

        high = np.ones([action_dim])
        self.action_space = gym.spaces.Box(-high, high)

        high = np.inf*np.ones([obs_dim])
        self.observation_space = gym.spaces.Box(-high, high)

        if self.RGB:
            self.rgb_space = gym.spaces.Box(low=0, high=255,
                                            shape=(self.VIDEO_W,
                                                   self.VIDEO_H,
                                                   3))

    def _seed(self, seed=None):
        self.np_random, seed = gym.utils.seeding.np_random(seed)
        return [seed]

    def _reset(self):
        if self.scene is None:
            ''' First reset '''
            self.scene = self.initialize_scene()
            # If load_xml_get_robot() is moved outside this condition after
            # env.reset all states become nan
            self.load_xml_get_robot()

        self.get_joint_dicts()
        self.robot_specific_reset()

        # Important Resets
        self.done = False
        self.frame = 0
        self.reward = 0

        for r in self.mjcf:
            r.query_position()

        self.camera = self.scene.cpp_world.new_camera_free_float(self.VIDEO_W, self.VIDEO_H, "video_camera")
        s = self.calc_state()
        self.potential = self.calc_potential()
        if self.RGB:
            rgb = self.get_rgb()
            return (s, rgb)
        else:
            return s

    def _render(self, mode, close):
        if close:
            return
        if mode=="human":
            self.scene.human_render_detected = True
            return self.scene.cpp_world.test_window()
        elif mode=="rgb_array":
            self.camera_adjust()
            rgb, _, _, _, _ = self.camera.render(False, False, False) # render_depth, render_labeling, print_timing)
            rendered_rgb = np.fromstring(rgb, dtype=np.uint8).reshape( (self.VIDEO_H,self.VIDEO_W,3) )
            return rendered_rgb
        else:
            assert(0)

    def _step(self, a):
        self.apply_action(a)  # Singleplayer (originally in a condition)
        self.scene.global_step()
        self.frame  += 1

        state = self.calc_state()  # also calculates self.joints_at_limit
        reward = self.calc_reward(a)
        done = self.stop_condition() # max frame reached?
        self.done = done
        if self.RGB:
            rgb = self.get_rgb()
            return state, rgb, reward, bool(done), {}
        else:
            return state, reward, bool(done), {}

    def HUD(self, s, a, done):
        self.scene.cpp_world.test_window_history_advance()
        self.scene.cpp_world.test_window_observations(s.tolist())
        self.scene.cpp_world.test_window_actions(a.tolist())
        self.scene.cpp_world.test_window_rewards(self.rewards)