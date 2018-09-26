import numpy as np
import tensorflow as tf

from utils import openai_entropy, mse, LearningRateDecay

class Actor():
    def __init__(self, state_size, action_size, reuse = False):
        super().__init__()
        self.state_size = state_size
        self.action_size = action_size

        with tf.variable_scope('Actor' if not reuse else "ShareLatent"):
            self.inputs = tf.placeholder(tf.float32, [None, self.state_size])
            self.actions = tf.placeholder(tf.int32, [None, self.action_size])
            self.advantages = tf.placeholder(tf.float32, [None, ])

            self.W_fc1 = self._fc_weight_variable([self.state_size, 256], name = "W_fc1")
            self.b_fc1 = self._fc_bias_variable([256], self.state_size, name = "b_fc1")
            self.fc1 = tf.nn.relu(tf.matmul(self.inputs, self.W_fc1) + self.b_fc1)

        with tf.variable_scope("Actions"):
            self.W_fc2 = self._fc_weight_variable([256, self.action_size], name = "W_fc2")
            self.b_fc2 = self._fc_bias_variable([self.action_size], 256, name = "b_fc2")

        self.logits = tf.matmul(self.fc1, self.W_fc2) + self.b_fc2

        self.pi = tf.nn.softmax(self.logits)
        self.neg_log_prob = tf.nn.softmax_cross_entropy_with_logits(logits = self.logits, labels = self.actions)
        self.policy_loss = tf.reduce_mean(self.neg_log_prob * self.advantages)

        self.variables = [self.W_fc1, self.b_fc1, self.W_fc2, self.b_fc2]

    def _fc_weight_variable(self, shape, name='W_fc'):
        input_channels = shape[0]
        d = 1.0 / np.sqrt(input_channels)
        initial = tf.random_uniform(shape, minval=-d, maxval=d)
        return tf.get_variable(name=name, dtype = tf.float32, initializer = initial)

    def _fc_bias_variable(self, shape, input_channels, name='b_fc'):
        d = 1.0 / np.sqrt(input_channels)
        initial = tf.random_uniform(shape, minval=-d, maxval=d)
        return tf.get_variable(name=name, dtype = tf.float32, initializer = initial)


class Critic():
    def __init__(self, state_size, reuse = False):
        super().__init__()
        self.state_size = state_size

        with tf.variable_scope('Critic' if not reuse else "ShareLatent" , reuse  = reuse):
            self.inputs = tf.placeholder(tf.float32, [None, self.state_size])
            self.returns = tf.placeholder(tf.float32, [None, ])

            self.W_fc1 = self._fc_weight_variable([self.state_size, 256], name = "W_fc1")
            self.b_fc1 = self._fc_bias_variable([256], self.state_size, name = "b_fc1")
            self.fc1 = tf.nn.relu(tf.matmul(self.inputs, self.W_fc1) + self.b_fc1)

        with tf.variable_scope("Value", reuse = False):
            self.W_fc2 = self._fc_weight_variable([256, 1], name = "W_fc3")
            self.b_fc2 = self._fc_bias_variable([1], 256, name = "b_fc3")

            self.value = tf.matmul(self.fc1, self.W_fc2) + self.b_fc2
            
        self.value_loss = tf.reduce_mean(mse(tf.squeeze(self.value), self.returns))
   
        self.variables = [self.W_fc1, self.b_fc1, self.W_fc2, self.b_fc2]
            
    def _fc_weight_variable(self, shape, name='W_fc'):
        input_channels = shape[0]
        d = 1.0 / np.sqrt(input_channels)
        initial = tf.random_uniform(shape, minval=-d, maxval=d)
        return tf.get_variable(name=name, dtype = tf.float32, initializer = initial)

    def _fc_bias_variable(self, shape, input_channels, name='b_fc'):
        d = 1.0 / np.sqrt(input_channels)
        initial = tf.random_uniform(shape, minval=-d, maxval=d)
        return tf.get_variable(name=name, dtype = tf.float32, initializer = initial)


class A2C():
    def __init__(self, 
                name, 
                state_size, 
                action_size, 
                entropy_coeff, 
                value_function_coeff, 
                max_gradient_norm, 
                alpha, 
                epsilon, 
                learning_rate = None, 
                decay = False, 
                reuse = False):

        self.max_gradient_norm  = max_gradient_norm
        self.entropy_coeff = entropy_coeff
        self.value_function_coeff = value_function_coeff
        self.state_size = state_size
        self.action_size = action_size
        self.reuse = reuse
        self.alpha = alpha
        self.epsilon = epsilon

        # Add this placeholder for having this variable in tensorboard
        self.mean_reward = tf.placeholder(tf.float32)
        self.tloss_summary = tf.placeholder(tf.float32)
        self.ploss_summary = tf.placeholder(tf.float32)
        self.vloss_summary = tf.placeholder(tf.float32)
        self.entropy_summary = tf.placeholder(tf.float32)
        self.steps_per_ep = tf.placeholder(tf.float32)
        
        with tf.variable_scope(name):
            self.actor = Actor(state_size = self.state_size, action_size = self.action_size, reuse = self.reuse)
            self.critic = Critic(state_size = self.state_size, reuse = self.reuse)

        self.learning_rate = tf.placeholder(tf.float32, [])
        self.fixed_lr = learning_rate
        self.decay = decay

        self.entropy = tf.reduce_mean(openai_entropy(self.actor.logits))
        self.total_loss = self.actor.policy_loss + self.critic.value_loss * self.value_function_coeff - self.entropy * self.entropy_coeff
        
        self.params = self.find_trainable_variables(name)
        self.grads = tf.gradients(self.total_loss, self.params)
        if self.max_gradient_norm is not None:
            self.grads, grad_norm = tf.clip_by_global_norm(self.grads, self.max_gradient_norm)

        # Apply Gradients
        self.grads = list(zip(self.grads, self.params))
        optimizer = tf.train.RMSPropOptimizer(learning_rate=self.learning_rate, decay=self.alpha,
                                              epsilon=self.epsilon)
        self.optimize = optimizer.apply_gradients(self.grads)

    def set_lr_decay(self, lr_rate, nvalues):
        self.learning_rate_decayed = LearningRateDecay(v = lr_rate,
                                                       nvalues = nvalues,
                                                       lr_decay_method='linear')
        print("Learning rate decay-er has been set up!")

    def find_trainable_variables(self, key, printing = False):
        with tf.variable_scope(key):
            variables = tf.trainable_variables()
            if printing:
                print(len(variables), variables)
            return variables

    def learn(self, sess, states, actions, returns, values):
        # Here we calculate advantage A(s,a) = R + yV(s') - V(s)
        # rewards = R + yV(s')
        advs = returns - values

        if self.decay:
            for i in range(len(states)):
                current_learning_rate = self.learning_rate_decayed.value()
        else:
            current_learning_rate = self.fixed_lr

        feed_dict = {
                        self.actor.inputs: states, 
                        self.critic.inputs: states, 
                        self.critic.returns: returns,
                        self.actor.actions: actions, 
                        self.actor.advantages: advs,
                        self.learning_rate: current_learning_rate,
                    }
        try:
            policy_loss, value_loss, policy_entropy, total_loss, _ = sess.run(
                [self.actor.policy_loss, self.critic.value_loss, self.entropy, self.total_loss, self.optimize],
                feed_dict = feed_dict
            )
        except ValueError:
            import sys
            print("States: ", states)
            print("Returns: ", returns)
            print("Actions: ", actions)
            print("Values: ", values)
            sys.exit()

        return policy_loss, value_loss, policy_entropy, total_loss

if __name__ == '__main__':
    a2c = A2C(100, 8, 0.05, 0.5, reuse = True)