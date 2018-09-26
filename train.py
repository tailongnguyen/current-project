import tensorflow as tf
import os 
import time
import argparse

from datetime import datetime
from network import *
from multitask_policy import MultitaskPolicy
from env.terrain import Terrain

ask = input('Would you like to create new log folder?Y/n\n')
if ask == '' or ask.lower() == 'y':
	log_name = input("New folder's name: ")
	TIMER = str(log_name).replace(" ", "_")
	# TIMER = str(datetime.now()).replace(' ', '_')
else:
	TIMER = sorted(os.listdir('logs/'))[-1]

def training(test_time, args):
	tf.reset_default_graph()
	
	if args.share_exp:
		network_name_scope = 'Share_samples'
	else:
		network_name_scope = 'None'

	env = Terrain(args.map_index, args.use_laser, args.immortal)
	policies = []
	
	for i in range(args.num_task):
		policy_i = A2C(
						name 					= 'A2C_' + str(i),
						state_size 				= env.cv_state_onehot.shape[1], 
						action_size 			= env.action_size, 
						entropy_coeff 			= args.entropy_coeff,
						value_function_coeff 	= args.value_function_coeff,
						max_gradient_norm		= args.max_gradient_norm,
						alpha 					= args.alpha,
						epsilon					= args.epsilon,
						learning_rate			= args.learning_rate,
						decay 					= args.decay,
						reuse					= bool(args.share_latent)
						)

		if args.decay:
			policy_i.set_lr_decay(args.learning_rate, args.num_epochs * args.num_episode * args.num_iters)
		
		print("\nInitialized network {}, with {} trainable weights.".format('A2C_' + str(i), len(policy_i.find_trainable_variables('A2C_' + str(i)))))
		policies.append(policy_i)

	gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction = 0.2)

	sess = tf.Session(config = tf.ConfigProto(gpu_options = gpu_options))
	sess.run(tf.global_variables_initializer())

	saver = tf.train.Saver()

	log_folder = 'logs/' + TIMER
	suffix = "_laser_" + str(args.use_laser) + '_immortal_' + str(args.immortal) + "_sharelatent_" + str(args.share_latent) + "_noise_" + str(args.noise_argmax)
	if not os.path.isdir(log_folder):
		os.mkdir(log_folder)
		os.mkdir(os.path.join(log_folder, 'None' + suffix))
		os.mkdir(os.path.join(log_folder, 'Share_samples' + suffix))
		
	if args.share_exp:
		writer = tf.summary.FileWriter(os.path.join(log_folder, "Share_samples" + suffix), sess.graph)
	else:
		writer = tf.summary.FileWriter(os.path.join(log_folder, 'None' + suffix), sess.graph)
	
	test_name =  "map_" + str(args.map_index) + "_test_" + str(test_time)
	tf.summary.scalar(test_name + "_rewards", tf.reduce_mean([policy.mean_reward for policy in policies], 0))
	tf.summary.scalar(test_name + "_tloss", tf.reduce_mean([policy.tloss_summary for policy in policies], 0))
	tf.summary.scalar(test_name + "_ploss", tf.reduce_mean([policy.ploss_summary for policy in policies], 0))
	tf.summary.scalar(test_name + "_vloss", tf.reduce_mean([policy.vloss_summary for policy in policies], 0))
	tf.summary.scalar(test_name + "_entropy", tf.reduce_mean([policy.entropy_summary for policy in policies], 0))
	tf.summary.scalar(test_name + "_nsteps", tf.reduce_mean([policy.steps_per_ep for policy in policies], 0))

	write_op = tf.summary.merge_all()

	multitask_agent = MultitaskPolicy(
										map_index 			= args.map_index,
										policies 			= policies,
										writer 				= writer,
										write_op 			= write_op,
										action_size 		= 8,
										num_task 			= args.num_task,
										num_iters 			= args.num_iters,
										num_episode 		= args.num_episode,
										num_epochs			= args.num_epochs,
										gamma 				= 0.99,
										plot_model 			= args.plot_model,
										save_model 			= args.save_model,
										save_name 			= network_name_scope + suffix,
										share_exp 			= args.share_exp,
										immortal			= args.immortal,
										use_laser			= args.use_laser,
										noise_argmax		= args.noise_argmax,
										timer 				= TIMER
									)

	multitask_agent.train(sess, saver)
	sess.close()


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Arguments')
	parser.add_argument('--num_tests', nargs='?', type=int, default = None, 
						help='Number of test to run')
	parser.add_argument('--map_index', nargs='?', type=int, default = None, 
						help='Index of map'),
	parser.add_argument('--num_task', nargs='?', type=int, default = 2, 
    					help='Number of tasks to train on')
	parser.add_argument('--share_exp', nargs='?', type=int, default = 0, 
    					help='Whether to turn on sharing samples on training')
	parser.add_argument('--share_latent', nargs='?', type=int, default = 0,
						help='Whether to join the latent spaces of actor and critic')
	parser.add_argument('--immortal', nargs='?', type=int, default = 0,
						help='Whether the agent dies when touching the wall, aka done episode')
	parser.add_argument('--num_episode', nargs='?', type=int, default = None,
    					help='Number of episodes to sample in each epoch')
	parser.add_argument('--num_iters', nargs='?', type=int, default = None,
						help='Number of steps to be sampled in each episode')
	parser.add_argument('--learning_rate', nargs='?', type=float, default = 5e-4,
						help='Learning rate')
	parser.add_argument('--use_laser', nargs='?', type=int, default = 0,
						help='Whether to use laser as input observation instead of one-hot vector')
	parser.add_argument('--num_epochs', nargs='?', type=int, default = None,
						help='Number of epochs to train')
	parser.add_argument('--entropy_coeff', nargs='?', type=float, default = 0.01,
						help='')
	parser.add_argument('--value_function_coeff', nargs='?', type=float, default = 0.5,
						help='')
	parser.add_argument('--max_gradient_norm', nargs='?', type=float, default = None,
						help='')
	parser.add_argument('--alpha', nargs='?', type=float, default = 0.99,
						help='Optimizer params')
	parser.add_argument('--epsilon', nargs='?', type=float, default = 1e-5,
						help='Optimizer params')
	parser.add_argument('--plot_model', nargs='?', type=int, default = 500,
						help='Plot interval')
	parser.add_argument('--decay', nargs='?', type=int, default = 1,
						help='Whether to decay the learning_rate')
	parser.add_argument('--noise_argmax', nargs='?', type=int, default = 1,
						help='Whether touse noise argmax in action sampling')
	parser.add_argument('--save_model', nargs='?', type=int, default = 500,
						help='Saving interval')
	args = parser.parse_args()

	start = time.time()
	for i in range(args.num_tests):
		training(i, args)

	print("Done in {} hours".format((time.time() - start)/3600))
