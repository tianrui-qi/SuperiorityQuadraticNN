import time
import numpy as np


class LNN:
    def __init__(self, dimension, neuron_num, activation_func):
        """
        :param dimension: dimension of sample point, int
        :param neuron_num: dictionary, { layer index : number of nodes }
            number of nodes for each layer, including hidden and output layers
        :param activation_func:dictionary, { layer index : function }
            the activation function after each layers' output, including hidden
            and output layers
        """
        # basic dimension parameter
        self.L = len(neuron_num)         # number of hidden & output layer
        self.D = dimension               # dimension of sample data point
        self.K = neuron_num[self.L - 1]  # number of Gaussian / classifications

        # network parameter
        self.neuron_num      = neuron_num
        self.activation_func = activation_func
        self.para            = {}

        # optimizer parameter
        self.h = {}     # for optimizer "AdaGrad", "RMSprop"
        self.m = {}     # for optimizer "Adam"
        self.v = {}     # for optimizer "Adam"

        self.initialize_network()

        # result
        self.iteration = []
        self.train_time = []
        self.train_loss = []
        self.valid_loss = []
        self.train_accuracy = []
        self.valid_accuracy = []
        self.train_precision = []
        self.valid_precision = []

    def initialize_network(self):
        """
        Initialize five dictionary of the parameters of object "LNN."

        See https://proceedings.mlr.press/v9/glorot10a/glorot10a.pdf (English)
            https://arxiv.org/abs/1502.01852 (English)
        about the initialization of parameter weighs and bias.
        """
        if len(self.activation_func) != self.L:
            print('Error! Dimension of the "activation_func" not match!')

        for l in range(self.L):
            if l == 0:
                node_from = self.D
            else:
                node_from = self.neuron_num[l - 1]
            node_to   = self.neuron_num[l]

            # sd for initialize weight 'w', parameter of network
            sd = 0.01
            """ # He initialization
            if self.activation_func[l] == self.sigmoid:
                sd = np.sqrt(1 / node_from)
            elif self.activation_func[l] == self.relu:
                sd = np.sqrt(2 / node_from)
            """

            # initialize parameters
            key = 'w' + str(l)
            self.para[key] = sd * np.random.randn(node_from, node_to)
            self.h[key] = np.zeros((node_from, node_to))
            self.m[key] = np.zeros((node_from, node_to))
            self.v[key] = np.zeros((node_from, node_to))

            key = 'b' + str(l)
            self.para[key] = np.zeros((1, node_to))
            self.h[key] = np.zeros((1, node_to))
            self.m[key] = np.zeros((1, node_to))
            self.v[key] = np.zeros((1, node_to))

    def load_NN(self, para, h, m, v):
        self.para, self.h, self.m, self.v = para, h, m, v

    """ Three Activation Functions """

    @staticmethod
    def relu(x):
        return np.maximum(0, x)

    @staticmethod
    def sigmoid(x):
        return 1 / (1 + np.exp(-x))

    @staticmethod
    def softmax(x):
        if x.ndim == 2:
            x = x.T
            x -= np.max(x, axis=0)
            y = np.exp(x) / np.sum(np.exp(x), axis=0)
            return y.T

        x -= np.max(x)
        return np.exp(x) / np.sum(np.exp(x))

    """ Two Gradient Calculator """

    def gradient_ng(self, point, label):
        """
        "Numerical Gradient"

        Get the gradient of all the parameter by just forward, no backward.
        The first loop is used to go through all the parameter.
        Inside the first loop is the numerical gradient of that parameter:
        give a small change 'h', see how f, the loss function, change.

        :param point: [ sample_size * D ], np.array
        :param label: [ sample_size * K ], np.array
        :return: dictionary, gradient for all the parameters
        """
        grad = {}
        for key in self.para.keys():
            h = 1e-4  # 0.0001

            grad[key] = np.zeros_like(self.para[key])

            it = np.nditer(self.para[key],
                           flags=['multi_index'], op_flags=['readwrite'])
            while not it.finished:
                idx = it.multi_index
                tmp_val = self.para[key][idx]

                self.para[key][idx] = float(tmp_val) + h
                fxh1 = self.CRE(point, label)  # f(x+h)

                self.para[key][idx] = float(tmp_val) - h
                fxh2 = self.CRE(point, label)  # f(x-h)

                grad[key][idx] = (fxh1 - fxh2) / (2 * h)

                self.para[key][idx] = tmp_val
                it.iternext()

        return grad

    def gradient_bp(self, point, label):
        """
        "Backpropagation"

        Use backpropagation to find every parameters' gradient with less time
        complexity than Numerical Gradient "gradient_ng".

        We first take forward step, which same to "predict", the only different
        is we record the "a" value using a dictionary since we need to use it
        during backward step.

        For each layer, we have three step:
             a_i  ---[w_i,b_i]--->  z_i  ---[activation_func]--->  a_(i+1)
        a_i: the input of the current layer, which is also the output of
             previous layer's z_(i-1).
        z_i: a_i * w_i + b_i
        a_(i+1): activation_function (z_i)

        In backward step, we just reverse all the step above
          da_i  <---[dw_i,db_i]---  dz_i  <---[d_activation_func]---  da_(i+1)
        The only difference is that the things we got now is "d", gradient.

        :param point: [ sample_size * D ], np.array
        :param label: [ sample_size * K ], np.array
        :return: dictionary, gradient for all the parameter
        """
        grad = {}

        # forward
        # a0 -> w0,b0 -> z0 -> a1 -> w1,b1 -> z1 -> a2
        a = {0: point}
        for l in range(self.L):
            z = np.dot(a[l], self.para['w' + str(l)]) + self.para['b' + str(l)]
            a[l + 1] = self.activation_func[l](z)

        # backward
        # da0 <- dw0,db0 <- dz0 <- da1 <- dw1,db1 <- dz1 <- da2
        da = 0
        for l in range(self.L-1, -1, -1):
            if self.activation_func[l] == self.softmax:     # softmax with loss
                dz = (a[l + 1] - label) / len(point)
            elif self.activation_func[l] == self.relu:      # relu
                dz = da * (a[l + 1] != 0)
            else:                                           # sigmoid
                dz = da * (1.0 - a[l + 1]) * a[l + 1]

            grad['w'+str(l)] = np.dot(a[l].T, dz)   # dw
            grad['b'+str(l)] = np.sum(dz, axis=0)   # db
            da = np.dot(dz, self.para['w'+str(l)].T)

        return grad

    """ Four Updating Methods """

    def SGD(self, grad, para):
        """
        "Stochastic Gradient Descent"

        Update all parameters including weighs and biases

        :param grad: dictionary
        :param para: dictionary, parameter that need for all optimizer
            ( will use "lr" )
        """
        for key in grad.keys():
            self.para[key] -= para["lr"] * grad[key]

    def AdaGrad(self, grad, para):
        """
        "Adaptive Gradient Algorithm", an improvement basis on "SGD" above

        Update all parameters including weighs and biases
        Can adjust learning rate by h
        At beginning, since the sum of squares of historical gradients is
        smaller, h += grads * grads the learning rate is high at first.
        As the sum of squares of historical gradients become larger, the
        learning rate will decrease

        :param grad:dictionary
        :param para: dictionary, parameter that need for all optimizer
            ( will use "lr" )
        """
        delta = 1e-7  # avoid divide zero
        for key in grad.keys():
            self.h[key] += np.square(grad[key] )
            self.para[key] -= para["lr"] * grad[key] / \
                              (np.sqrt(self.h[key]) + delta)

    def RMSprop(self, grad, para):
        """
        "Root Mean Squared Propagation", an improvement basis on "AdaGrad" above

        See "https://zhuanlan.zhihu.com/p/34230849" (Chinese)

        Update all parameters including weighs and biases
        Use "decay_rate" to control how much historical information (h) is
        retrieved.
        When the sum of squares of historical gradients is smaller,
        which means that the parameters space is gentle, (h) will give a larger
        number, which will increase the learning rate.
        When the sum of squares of historical gradients is larger, which means
        that the parameters space is steep, (h) will give a smaller number,
        which will decrease the learning rate.

        :param grad: dictionary
        :param para: dictionary, parameter that need for all optimizer
            ( will use "lr", "decay_rate" )
        """
        delta = 1e-7  # avoid divide zero
        for key in grad.keys():
            self.h[key] *= para["decay_rate"]
            self.h[key] += (1.0 - para["decay_rate"]) * np.square(grad[key])
            self.para[key] -= para["lr"] * grad[key] / \
                              (np.sqrt(self.h[key]) + delta)

    def Adam(self, grad, para):
        """
        "Adaptive Moment Estimation", an improvement basis on "RMSprop" above
        and momentum

        See "https://arxiv.org/abs/1412.6980v8" (English)

        :param grad: dictionary
        :param para: dictionary, parameter that need for all optimizer
            ( will use "lr", "beta1", "beta2", "iter" )
        """
        para["iter"] += 1
        lr_t = para["lr"] * np.sqrt(1.0 - para["beta2"]**para["iter"]) / \
               (1.0 - para["beta1"]**para["iter"])
        delta = 1e-7  # avoid divide zero
        for key in grad.keys():
            self.m[key] += (1.0 - para["beta1"]) * (grad[key] - self.m[key])
            self.v[key] += (1.0 - para["beta2"]) * (grad[key]**2 - self.v[key])
            self.para[key] -= lr_t*self.m[key] / (np.sqrt(self.v[key]) + delta)

    """ Trainer """

    def train(self, train_point, train_label, optimizer_para,
              valid_point=None, valid_label=None, optimizer=RMSprop,
              epoch=20000, stop_point=200):
        """
        Use a gradient calculator to calculate the gradient of each parameter
        and then use optimizer to update parameters.

        Args:
            train_point: [ sample_size * D ], np.array
            train_label: [ sample_size * K ], np.array
            optimizer_para: the parameter dictionary for the optimizer
            valid_point: [ sample_size * D ], np.array
            valid_label: [ sample_size * K ], np.array
            optimizer: choose which optimizer will be use
            epoch: number of iteration
            stop_point: stop training after "stop_point" number of
            iteration such that the accuracy of validation set does not increase
        """
        time_track = 0
        stop_track = 0
        loss_max = 1000
        for i in range(epoch):
            if stop_point <= stop_track: break

            begin = time.time()

            # Main part ========================================================
            optimizer(self.gradient_bp(train_point, train_label),
                      optimizer_para)
            # ==================================================================

            time_track += time.time() - begin
            self.train_time.append(time_track)

            """ Recording """

            self.iteration.append(i)
            if train_label is not None:
                self.train_loss.append(self.CRE(train_point, train_label))
                self.train_accuracy.append(self.accuracy(train_point, train_label))
                self.train_precision.append(self.precision(train_point, train_label))
            if valid_label is not None:
                self.valid_loss.append(self.CRE(valid_point, valid_label))
                self.valid_accuracy.append(self.accuracy(valid_point, valid_label))
                self.valid_precision.append(self.precision(valid_point, valid_label))
            # print("{}\t{}".format(i, self.valid_accuracy[-1]))

            """ Early Stopping """

            if valid_label is None: continue
            if self.valid_loss[-1] < loss_max:
                stop_track = 0
                loss_max = self.valid_loss[-1]
            else:
                stop_track += 1

    """ Estimator """

    def predict(self, point):
        """
        Take "sample_point" as the network's input. Using the current network
        parameters to predict the label of the "sample_point." Notes that the
        return value is not the true label like [ 0 0 1 0]. It's the score of
        each value [ 10 20 30 5 ]. To get the label, still need to take argmax
        of return value "z"

        :param point:  [ sample_size * D ], np.array
        :return: [ sample_size * K ], np.array
        """
        a = point   # [ N * K ], np.array
        for l in range(self.L):
            z = np.dot(a, self.para['w'+str(l)]) + self.para['b'+str(l)]
            a = self.activation_func[l](z)
        return a    # [ N * K ], np.array

    def CRE(self, point, label):
        """
        Return the cross entropy error (CRE).
        """
        # 1. check the input data
        if len(point[0]) != self.D or len(label[0]) != self.K: return 0

        # 2. compute the loss
        y = self.predict(point)     # predict label
        t = label                   # actual label
        return -(np.sum(np.multiply(t, np.log(y + 1e-10))) / point.shape[0])

    def accuracy(self, point, label):
        """
        Return the accuracy.
        """
        # 1. check the input data
        if len(point[0]) != self.D or len(label[0]) != self.K: return 0

        # 2. compute the accuracy
        t = np.argmax(label, axis=1)                # actual label
        y = np.argmax(self.predict(point), axis=1)  # predict label
        return np.sum(y == t) / len(label)  # accuracy, float

    def precision(self, point, label):
        """
        Compute the precision of each cluster and return the average precision.
        """
        # 1. check the input data
        if len(point[0]) != self.D or len(label[0]) != self.K: return 0

        # 2. compute the precision
        t = np.argmax(label, axis=1)                # actual label
        y = np.argmax(self.predict(point), axis=1)  # predict label
        precision = 0
        for k in range(self.K):     # find the precision of each cluster
            TP = 0  # Predict class == k, Actual class == k
            FP = 0  # Predict class == k, Actual class != k
            for n in range(len(point)):
                if y[n] != k: continue      # means predict class != k
                if t[n] == y[n]: TP += 1    # Actual class == k
                if t[n] != y[n]: FP += 1    # Actual class != k
            precision += TP / (TP + FP)
        return precision / self.K           # average precision
