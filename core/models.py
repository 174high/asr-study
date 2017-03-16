from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import core.ctc_utils as ctc_utils
from utils.hparams import HParams

import keras
import keras.backend as K
from keras.initializers import uniform
from keras.activations import relu

from keras.models import Model

from keras.layers import Input
from keras.layers import GaussianNoise
from keras.layers import TimeDistributed
from keras.layers import Dense
from .layers import LSTM
from keras.layers import Masking
from keras.layers import Bidirectional
from keras.layers import Lambda
from keras.layers import Dropout
from keras.layers import merge

from keras.regularizers import l1, l2, l1_l2

from .layers import recurrent


def ctc_model(inputs, output, **kwargs):
    """ Given the input and output returns a model appending ctc_loss, the
    decoder, labels, and inputs_length

    # Arguments
        see core.ctc_utils.layer_utils.decode for more arguments
    """

    # Define placeholders
    labels = Input(name='labels', shape=(None,), dtype='int32', sparse=True)
    inputs_length = Input(name='inputs_length', shape=(None,), dtype='int32')

    # Define a decoder
    dec = Lambda(ctc_utils.decode, output_shape=ctc_utils.decode_output_shape,
                 arguments={'is_greedy': True}, name='decoder')
    y_pred = dec([output, inputs_length])

    loss = ctc_utils.ctc_loss(output, labels, input_length)

    model = Model(input=[inputs, labels, inputs_length], output=y_pred)
    model.add_loss(loss)

    return model


def graves2006(num_features=26, num_hiddens=100, num_classes=28, std=.6):
    """ Implementation of Graves' model
    Reference:
        [1] Graves, Alex, et al. "Connectionist temporal classification:
        labelling unsegmented sequence data with recurrent neural networks."
        Proceedings of the 23rd international conference on Machine learning.
        ACM, 2006.
    """

    x = Input(name='inputs', shape=(None, num_features))
    o = x

    o = GaussianNoise(std)(o)
    o = Bidirectional(LSTM(num_hiddens,
                      return_sequences=True,
                      implementation=0))(o)
    o = TimeDistributed(Dense(num_classes))(o)

    return ctc_model(x, o)


def eyben(num_features=39, num_hiddens=[78, 120, 27], num_classes=28):
    """ Implementation of Eybens' model
    Reference:
        [1] Eyben, Florian, et al. "From speech to letters-using a novel neural
        network architecture for grapheme based asr." Automatic Speech
        Recognition & Understanding, 2009. ASRU 2009. IEEE Workshop on. IEEE,
        2009.
    """

    assert len(num_hiddens) == 3

    x = Input(name='inputs', shape=(None, num_features))
    o = x

    if num_hiddens[0]:
        o = TimeDistributed(Dense(num_hiddens[0]))(o)
    if num_hiddens[1]:
        o = Bidirectional(LSTM(num_hiddens[1],
                          return_sequences=True,
                          implementation=0))(o)
    if num_hiddens[2]:
        o = Bidirectional(LSTM(num_hiddens[2],
                          return_sequences=True,
                          implementation=0))(o)

    o = TimeDistributed(Dense(num_classes))(o)

    return ctc_model(x, o)


def maas(num_features=81, num_classes=29, num_hiddens=1824, dropout=0.1,
         max_value=20):
    """ Maas' model.
    Reference:
        [1] Maas, Andrew L., et al. "Lexicon-Free Conversational Speech
        Recognition with Neural Networks." HLT-NAACL. 2015.
    """

    x = Input(name='inputs', shape=(None, num_features))
    o = x

    def clipped_relu(x):
        return relu(x, max_value=max_value)

    # First layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)

    # Second layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)

    # Third layer
    o = Bidirectional(SimpleRNN(num_hiddens, return_sequences=True,
                                dropout=dropout,
                                activation=clipped_relu,
                                kernel_initializer='he_normal'),
                      merge_mode='sum')(o)

    # Fourth layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)

    # Fifth layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)

    # Output layer
    o = TimeDistributed(Dense(num_classes))(o)

    return ctc_model(x, o)


def deep_speech(num_features=81, num_classes=29, num_hiddens=2048, dropout=0.1,
                max_value=20):
    """ Deep Speech model.

        Contains five layers: 3 FC - BRNN - 1 FC
        Dropout only applied to fully connected layers (between 5% to 10%)

    Note:
        * We are not translating the raw audio files by 5 ms (Sec 2.1 in [1])
        * We are not striding the RNN to halve the timesteps (Sec 3.3 in [1])
        * We are not using frames of context
        * Their output contains {a, ..., z, space, apostrophe, blank}
    Experiment 5.1: Conversational speech: Switchboard Hub5'00 (full)
        * Input - 80 linearly spaced log filter banks and an energy term. The
        filter banks are computed over windows of 20ms strided by 10ms.
        * Speaker adaptation - spectral features are normalized on a per
        speaker basis.
        * Hidden units: {2304, 2048}
        * Essemble of 4 networks
    Experiment 5.2: Noisy speech
        * Input - 160 linearly spaced log filter banks. The filter banks are
        computed over windows of 20ms strided by 10ms. Global mean and standard
        deviation over training set normalization
        * Speaker adaptation - none
        * Hidden units: 2560
        * Essemble of 6 networks
    Reference:
        [1] HANNUN, A. Y. et al. Deep Speech: Scaling up end-to-end speech
        recognition. arXiV, 2014.
    """
    x = Input(name='inputs', shape=(None, num_features))
    o = x

    def clipped_relu(x):
        return relu(x, max_value=max_value)

    # First layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)
    o = TimeDistributed(Dropout(dropout))(o)

    # Second layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)
    o = TimeDistributed(Dropout(dropout))(o)

    # Third layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)
    o = TimeDistributed(Dropout(dropout))(o)

    # Fourth layer
    o = Bidirectional(SimpleRNN(num_hiddens, return_sequences=True,
                                dropout=dropout,
                                activation=clipped_relu,
                                kernel_initializer='he_normal'),
                      merge_mode='sum')(o)
    o = TimeDistributed(Dropout(dropout))(o)

    # Fifth layer
    o = TimeDistributed(Dense(num_hiddens))(o)
    o = TimeDistributed(Activation(clipped_relu))(o)
    o = TimeDistributed(Dropout(dropout))(o)

    # Output layer
    o = TimeDistributed(Dense(num_classes))(o)

    return ctc_model(x, o)


def brsmv1(num_features=39, num_classes=28, num_hiddens=256, num_layers=5,
           dropout=0.2, zoneout=0., input_dropout=False,
           input_std_noise=.0, weight_decay=1e-4, residual=None,
           layer_norm=None, mi=None, activation='tanh'):
    """ BRSM v1.0
    Improved features:
        * Residual connection
        * Variational Dropout
        * Zoneout
        * Layer Normalization
        * Multiplicative Integration
    Note:
        Dropout, zoneout and weight decay is tied through layers, in order to
        minimizing the number of hyper parameters
    Reference:
        [1] Gal, Y, "A Theoretically Grounded Application of Dropout in
        Recurrent Neural Networks", 2015.
        [2] Graves, Alex, Abdel-rahman Mohamed, and Geoffrey Hinton. "Speech
        recognition with deep recurrent neural networks", 2013.
        [3] Krueger, David, et al. "Zoneout: Regularizing rnns by randomly
        preserving hidden activations", 2016.
        [4] Ba, Jimmy Lei, Jamie Ryan Kiros, and Geoffrey E. Hinton. "Layer
        normalization.", 2016.
        [5] Wu, Yuhuai, et al. "On multiplicative integration with recurrent
        neural networks." Advances In Neural Information Processing Systems.
        2016.
        [6] Wu, Yonghui, et al. "Google's Neural Machine Translation System:
        Bridging the Gap between Human and Machine Translation.", 2016.
    """

    x = Input(name='inputs', shape=(None, num_features))
    o = x

    if input_std_noise is not None:
        o = GaussianNoise(input_std_noise)(o)

    if input_dropout:
        o = Dropout(dropout)(o)

    for i, _ in enumerate(range(num_layers)):
        new_o = Bidirectional(LSTM(num_hiddens,
                                   return_sequences=True,
                                   kernel_regularizer=l2(weight_decay),
                                   recurrent_regularizer=l2(weight_decay),
                                   dropout=dropout,
                                   recurrent_dropout=dropout,
                                   zoneout_c=zoneout,
                                   zoneout_h=zoneout,
                                   mi=mi,
                                   layer_norm=layer_norm,
                                   activation=activation))(o)

        if residual is not None and i != 0:
            o = merge([new_o,  o], mode=residual)
        else:
            o = new_o

    o = TimeDistributed(Dense(num_classes,
                              kernel_regularizer=l2(weight_decay)))(o)

    return ctc_model(x, o)
