from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
# Preventing pool_allocator message
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import argparse
import h5py
import inspect

from preprocessing import audio, text
from common import utils
from common.dataset_generator import DatasetGenerator
from common.hparams import HParams

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluating an ASR system.')

    parser.add_argument('--model', required=True, type=str)
    parser.add_argument('--dataset', required=True, type=str)
    parser.add_argument('--batch_size', default=32, type=int)

    # Features generation (if necessary)
    parser.add_argument('--feats', type=str, default='raw',
                        choices=['mfcc', 'raw', 'logfbank'])
    parser.add_argument('--feats_params', type=str, default='{}')

    # Label generation (if necessary)
    parser.add_argument('--text_parser', type=str,
                        default='simple_char_parser')
    parser.add_argument('--text_parser_params', type=str, default='{}')

    # Other configs
    parser.add_argument('--gpu', default='0', type=str)
    parser.add_argument('--allow_growth', default=False, action='store_true')

    args = parser.parse_args()
    args_nondefault = utils.parse_nondefault_args(
        args, parser.parse_args(
            ['--model', args.model, '--dataset', args.dataset]))

    # GPU configuration
    utils.config_gpu(args.gpu, args.allow_growth)

    # Loading model
    model, meta = utils.load_model(args.model, return_meta=True, mode='eval')

    args = HParams(
        from_str=str(meta['training_args'])).update(vars(args_nondefault))

    # Features extractor
    feats_extractor = utils.get_from_module('preprocessing.audio',
                                            args.feats,
                                            args.feats_params)

    # Recovering text parser
    text_parser = utils.get_from_module('preprocessing.text',
                                        args.text_parser,
                                        args.text_parser_params)

    data_gen = DatasetGenerator(feats_extractor, text_parser,
                                batch_size=args.batch_size, seed=0)
    test_flow = data_gen.flow_from_fname(args.dataset, dt_name='test')

    metrics = model.evaluate_generator(test_flow, test_flow.len,
                                       max_q_size=10, nb_worker=1)

    for m, v in zip(model.metrics_names, metrics):
        print('%s: %4f' % (m, v))
