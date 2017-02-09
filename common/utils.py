from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import h5py
import sys
import os

import logging
import logging.config
import yaml

import numpy as np
from scipy import sparse


import keras.backend as K
import tensorflow as tf

import keras

import inspect
import yaml

import core


from .hparams import HParams


logger = logging.getLogger(__name__)


def safe_mkdirs(path):
    ''' Safe makedirs
    Directory is created with command `makedir -p`.
    Returns:
        `path` if the directory already exists or is created
    Exception:
        OSError if something is wrong
    '''
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno != 17:  # 17 = file exists
            raise

    return path


def get_from_module(module, name):
    members = inspect_module(module)

    if name is None or name.lower() == 'none':
        return None

    members = {k.lower().strip(): v for k, v in members.items()}

    try:
        return members[name.lower().strip()]
    except KeyError, e:
        raise KeyError("%s not found in %s.\n Valid values are: %s" %
                       (name, module, ', '.join(members.keys())))


def inspect_module(module, to_dict=True):
    members = inspect.getmembers(sys.modules[module], lambda member:
                                 hasattr(member, '__module__') and
                                 member.__module__ == module)
    if to_dict:
        return dict(members)

    return members


def get_custom_objects():
    """ Verify all custom object that may be used to load a keras model
    """
    all_custom_objects = []
    for module in ['core.layers', 'core.layers_utils',
                   'core.metrics', 'core.ctc_utils']:
        all_custom_objects.extend(inspect_module(module, to_dict=False))

    return dict(all_custom_objects)


def load_meta(model_fname):
    meta = {}
    with h5py.File(model_fname, 'r') as f:
        meta_group = f['meta']

        meta['training_args'] = yaml.load(
            meta_group.attrs['training_args'])
        for k in meta_group.keys():
            meta[k] = list(meta_group[k])

    return meta


def load_model(model_fname, return_meta=False):
    """ Loading keras model with custom objects
    """
    model = keras.models.load_model(model_fname,
                                    custom_objects=get_custom_objects())

    if return_meta:
        meta = load_meta(model_fname)
        return model, meta

    return model


def ld2dl(ld):
    '''Transform a list of dictionaries in a dictionaries with lists
    # Note
        All dictionaries have the same keys
    '''
    return dict(zip(ld[0], zip(*[d.values() for d in ld])))


def config_gpu(gpu, allow_growth=False, log_device_placement=False):
    # Choosing gpu
    if gpu == '-1':
        config = tf.ConfigProto(device_count={'GPU': 0},
                                log_device_placement=log_device_placement)
    else:
        if gpu == 'all':
            gpu = ''
        config = tf.ConfigProto(log_device_placement=log_device_placement)
        config.gpu_options.visible_device_list = gpu
    if allow_growth:  # dynamic gpu memory allocation
        config.gpu_options.allow_growth = True
    session = tf.Session(config=config)
    K.set_session(session)


def parse_nondefault_args(args, default_args):
    # removing default arguments
    args_default = {k: v for k, v in vars(default_args).items()
                    if k not in [arg.split('-')[-1] for arg in sys.argv
                                 if arg.startswith('-')]}
    args_nondefault = {k: v for k, v in vars(args).items()
                       if k not in args_default or args_default[k] != v}

    args_nondefault = HParams(from_str=str(args_nondefault))

    return args_nondefault


def setup_logging(default_path='logging.yaml', default_level=logging.INFO,
                  env_key='LOG_CFG'):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
