import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as opt

import matplotlib.pyplot as plt

import numpy as np

import gymnasium as gym

import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

# %%

class DQN(nn.Module):
    def __init__(self, lr, input_dims, fc1_dims, fc2_dims, n_actions):
        super(DQN, self).__init__()

        self.input_dims = input_dims
        self.fc1_dims = fc1_dims
        self.fc2_dims = fc2_dims
        self.n_actions = n_actions
        
        self.fc1 = nn.Linear(*self.input_dims, self.fc1_dims)
        self.fc2 = nn.Linear(self.fc1_dims, self.fc2_dims)
        self.fc3 = nn.Linear(self.fc2_dims, self.n_actions)

        self.optimizer = opt.AdamW(self.parameters(), lr=lr)

        self.loss = nn.MSELoss()

        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.to(self.device)

        print("self.device", self.device)
        print("torch.cuda.get_device_name(0) = ", torch.cuda.get_device_name(0))

    def forward(self, state):
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        actions = self.fc3(x)
        
        return actions
    
# %%

class Agent():
    def __init__(self, 
                 lr, 
                 input_dims, 
                 n_actions,
                 gamma=0.99, 
                 epsilon=1.0, 
                 batch_size=64, 
                 max_mem_size=100000, 
                 eps_end=0.01, 
                 eps_dec=0.995):
        
        print("learning rate = ", lr)
        print("action dimension = ", n_actions)
        print("observation dimension = ", *input_dims)

        self.gamma = gamma
        
        self.epsilon = epsilon
        self.eps_min = eps_end
        self.eps_dec = eps_dec

        self.lr = lr
        
        self.action_space = [i for i in range(n_actions)]

        self.mem_size = max_mem_size
        self.batch_size = batch_size
        self.mem_counter = 0

        self.q_eval = DQN(self.lr, n_actions=n_actions, input_dims = input_dims, fc1_dims=256, fc2_dims=256)

        self.state_memory = np.zeros((self.mem_size, *input_dims), dtype=np.float32)
        self.new_state_memory = np.zeros((self.mem_size, *input_dims), dtype=np.float32)

        self.action_memory = np.zeros(self.mem_size, dtype=np.int32)
        self.reward_memory = np.zeros(self.mem_size, dtype=np.float32)
        self.terminal_memory = np.zeros(self.mem_size, dtype=bool)

    def store_transition(self, state, action, reward, state_new, done):
        index = self.mem_counter % self.mem_size

        self.state_memory[index] = state[0]
        self.new_state_memory[index] = state_new
        self.action_memory[index] = action
        self.reward_memory[index] = reward
        self.terminal_memory[index] = done

        self.mem_counter += 1

    def choose_action(self, observation):
        if np.random.random() > self.epsilon:
        # exploitation
            # if observation is a tuple, change it back to array
            # idky
            if type(observation) is tuple:
                observation = observation[0]

            state = torch.tensor([observation]).to(self.q_eval.device)
            actions = self.q_eval.forward(state)
            action = torch.argmax(actions).item()
        else:
        # exploration
            # action = np.random.choice(self.action_space) # can also use env.action_space.sample() from gym
            action = env.action_space.sample()

        return action
    
    def learn(self):
        # learn as soon as the batch_size is filled up
        if self.mem_counter < self.batch_size:
            return
        
        self.q_eval.optimizer.zero_grad()

        max_mem = min(self.mem_counter, self.mem_size)
        batch = np.random.choice(max_mem, self.batch_size, replace=False) #replace = False so that we don't choose the same things again

        batch_index = np.arange(self. batch_size, dtype=np.int32)

        state_batch = torch.tensor(self.state_memory[batch]).to(self.q_eval.device)
        new_state_batch = torch.tensor(self.new_state_memory[batch]).to(self.q_eval.device)
        reward_batch = torch.tensor(self.reward_memory[batch]).to(self.q_eval.device)
        terminal_batch = torch.tensor(self.terminal_memory[batch]).to(self.q_eval.device)

        action_batch = self.action_memory[batch] # doesn't need to be a tensor

        q_eval = self.q_eval.forward(state_batch)[batch_index, action_batch]
        q_next = self.q_eval.forward(new_state_batch)
        q_next[terminal_batch] = 0.0

        q_target = reward_batch + self.gamma * torch.max(q_next, dim=1)[0]
        # q_target = q_target*-1
        # print("q_eval = ", q_eval)
        # print("tarch max = ", torch.max(q_next, dim=1)[0])

        loss = self.q_eval.loss(q_target, q_eval).to(self.q_eval.device)
        loss.backward()
        self.q_eval.optimizer.step()

        # decay epsilon
        # self.epsilon = self.epsilon - self.eps_dec if self.epsilon > self.eps_min else self.eps_min
        self.epsilon = max(self.eps_min, self.eps_dec * self.epsilon)

# %%

# env  = gym.make("LunarLander-v2", render_mode="human")
env = gym.make("LunarLander-v2")
env = gym.wrappers.RecordEpisodeStatistics(env, 50)  # Records episode-reward

# %%

agent = Agent(lr=0.0001,
              input_dims=[env.observation_space.shape[0]],
              n_actions=env.action_space.n,
              )

scores, eps_history = [], []
n_games = int(5e3)  # Total number of episodes

for i in range (n_games):
    score = 0
    done = False
    # observation = env.reset(options={"randomize": False})
    observation = env.reset()

    while not done:
        action = agent.choose_action(observation)
        
        observation, reward, terminated, truncated, info = env.step(action)

        score += reward
        agent.store_transition(observation, action, reward, observation, done)

        agent.learn()

        if terminated or truncated:
            done = True

    scores.append(score)
    eps_history.append(agent.epsilon)

    average_score = np.mean(scores[-100:])

    if i % 10 == 0:
        print("episode", i, "score %.2f" % score, "average_score %0.2f" % average_score, "epsilon %.2f" % agent.epsilon)

X = [i + 1 for i in range (n_games)]
    
# %%

# Create figure and axes
fig, ax1 = plt.subplots()

# Plot x vs y on the left y-axis
ax1.plot(X, scores, 'b-', label='score')
ax1.set_xlabel('x')
ax1.set_ylabel('score', color='b')

# Create a second y-axis on the right
ax2 = ax1.twinx()
# Plot x vs z on the right y-axis
ax2.plot(X, eps_history, 'r--', label='epsilon')
ax2.set_ylabel('epsilon', color='r')

# Add legend
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

plt.title("lr = " + str(agent.lr) + "; decay = " + str(agent.eps_dec) + "; n_games = " + str(n_games))

plt.show()