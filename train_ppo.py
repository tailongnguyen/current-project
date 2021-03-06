import tensorflow as tf
import os 
import time
import argparse
import sys

from datetime import datetime
from network import *
from multitask_policy import MultitaskPolicy
from runner_ppo import Runner

from env.terrain import Terrain

ask = input('Would you like to create new log folder?Y/n ')
if ask == '' or ask.lower() == 'y':
	log_name = input("New folder's name: ")
	TIMER = str(datetime.now()).replace(' ', '_').replace(":", '-').split('.')[0] + "_" + str(log_name).replace(" ", "_")
else:
	dirs = [d for d in os.listdir('logs/') if os.path.isdir('logs/' + d)]
	TIMER = sorted(dirs, key=lambda x: os.path.getctime('logs/' + x), reverse=True)[0]

def train(args):
	log_folder = 'logs/' + TIMER

	suffix = []
	for arg in vars(args):
		exclude = ['num_tests', 'map_index', 'plot_model', 'save_model', 'num_epochs', 'max_gradient_norm', 'alpha', 'epsilon']
		if arg in exclude:
			continue

		boolean = ['share_exp', 'share_latent', 'use_laser', 'use_gae', 'immortal', 'decay', 'noise_argmax']
		if arg in boolean:
			if getattr(args, arg) != 1:
				continue
			else:
				suffix.append(arg)
				continue

		if arg in ['share_decay'] and getattr(args, 'share_exp') == 0:
			continue
			
		suffix.append(arg + "_" + str(getattr(args, arg)))

	suffix = '-'.join(suffix)

	if not os.path.isdir(log_folder):
		os.mkdir(log_folder)

	if os.path.isdir(os.path.join(log_folder, suffix)):
		print("Log folder already exists. Continue training ...")
		test_time = len(os.listdir(os.path.join(log_folder, suffix)))
	else:
		os.mkdir(os.path.join(log_folder, suffix))
		test_time = 0
	
	if test_time == 0:
		writer = tf.summary.FileWriter(os.path.join(log_folder, suffix))
	else:
		writer = tf.summary.FileWriter(os.path.join(log_folder, suffix))
	
	test_name =  "map_" + str(args.map_index) + "_test_" + str(test_time)

	runner = Runner(args = args,
					writer = writer,
					gamma = 0.99,
					lamb = 0.95,
					test_name = test_name,
					save_name = test_name + "_" + suffix,
					timer = TIMER
					)
					
	runner.train()

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Arguments')
	parser.add_argument('--num_tests', nargs='?', type=int, default = 1, 
						help='Number of test to run')
	parser.add_argument('--map_index', nargs='?', type=int, default = 4, 
						help='Index of map'),
	parser.add_argument('--num_task', nargs='?', type=int, default = 1, 
    					help='Number of tasks to train on')
	parser.add_argument('--immortal', nargs='?', type=int, default = 0, 
    					help='Whether the agent dies when hitting the wall')
	parser.add_argument('--share_exp', nargs='?', type=int, default = 0, 
    					help='Whether to turn on sharing samples on training')
	parser.add_argument('--share_cut', nargs='?', type=int, default = 0, 
    					help='Whether to cut the sharing from some epoch onwards')
	parser.add_argument('--share_latent', nargs='?', type=int, default = 1,
						help='Whether to join the latent spaces of actor and critic')
	parser.add_argument('--num_episode', nargs='?', type=int, default = 10,
    					help='Number of episodes to sample in each epoch')
	parser.add_argument('--num_iters', nargs='?', type=int, default = None,
						help='Number of steps to be sampled in each episode')
	parser.add_argument('--lr', nargs='?', type=float, default = 0.005,
						help='Learning rate')
	parser.add_argument('--clip_param', nargs='?', type=float, default = 0.2,
						help='Clip range of ppo loss')
	parser.add_argument('--use_laser', nargs='?', type=int, default = 0,
						help='Whether to use laser as input observation instead of one-hot vector')
	parser.add_argument('--use_gae', nargs='?', type=int, default = 1,
						help='Whether to use generalized advantage estimate')
	parser.add_argument('--num_epochs', nargs='?', type=int, default = 2000,
						help='Number of epochs to train')
	parser.add_argument('--share_decay', nargs='?', type=float, default = 1.0,
						help='threshold when sharing samples')
	parser.add_argument('--ec', nargs='?', type=float, default = 0.01,
						help='Entropy coeff in total loss')
	parser.add_argument('--vc', nargs='?', type=float, default = 0.5,
						help='Value loss coeff in total loss')
	parser.add_argument('--max_gradient_norm', nargs='?', type=float, default = None,
						help='')
	parser.add_argument('--alpha', nargs='?', type=float, default = 0.99,
						help='Optimizer params')
	parser.add_argument('--epsilon', nargs='?', type=float, default = 1e-5,
						help='Optimizer params')
	parser.add_argument('--plot_model', nargs='?', type=int, default = 1000,
						help='Plot interval')
	parser.add_argument('--decay', nargs='?', type=int, default = 0,
						help='Whether to decay the learning_rate')
	parser.add_argument('--noise_argmax', nargs='?', type=int, default = 1,
						help='Whether touse noise argmax in action sampling')
	parser.add_argument('--save_model', nargs='?', type=int, default = 500,
						help='Saving interval')
	parser.add_argument('--ppo_epochs', nargs='?', type=int, default = 4,
						help='Number of epochs to perform ppo update')
	parser.add_argument('--minibatch', nargs='?', type=int, default = 5,
						help='Minibatch size of ppo update')
	

	args = parser.parse_args()

	start = time.time()
	for i in range(args.num_tests):
		train(args)

	print("Done in {} minutes".format((time.time() - start)/60))

