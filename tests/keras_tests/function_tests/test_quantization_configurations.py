# Copyright 2021 Sony Semiconductors Israel, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================


from model_compression_toolkit.keras.default_framework_info import DEFAULT_KERAS_INFO
import unittest
import numpy as np
import model_compression_toolkit as mct
import tensorflow as tf
from tensorflow.keras import layers
import itertools


def model_gen():
    inputs = layers.Input(shape=[16, 16, 3])
    x = layers.Conv2D(2, 3, padding='same')(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Activation('relu')(x)
    return tf.keras.models.Model(inputs=inputs, outputs=x)


class TestQuantizationConfigurations(unittest.TestCase):
    def test_run_quantization_config_mbv1(self):
        x = np.random.randn(1, 16, 16, 3)

        def representative_data_gen():
            return [x]

        quantizer_methods = [mct.QuantizationMethod.POWER_OF_TWO,
                             mct.QuantizationMethod.SYMMETRIC,
                             mct.QuantizationMethod.UNIFORM]
        quantization_error_methods = [mct.QuantizationErrorMethod.MSE,
                                      mct.QuantizationErrorMethod.NOCLIPPING,
                                      mct.QuantizationErrorMethod.MAE,
                                      mct.QuantizationErrorMethod.LP,
                                      mct.QuantizationErrorMethod.KL]
        bias_correction = [True, False]
        relu_unbound_correction = [True, False]
        input_scaling = [True, False]
        weights_per_channel = [True, False]
        shift_negative_correction = [True, False]

        weights_config_list = [quantizer_methods, quantization_error_methods, bias_correction, weights_per_channel,
                               input_scaling]
        weights_test_combinations = list(itertools.product(*weights_config_list))

        activation_config_list = [quantizer_methods, quantization_error_methods, relu_unbound_correction,
                                  shift_negative_correction]
        activation_test_combinations = list(itertools.product(*activation_config_list))

        model = model_gen()
        for quantize_method, error_method, bias_correction, per_channel, input_scaling in weights_test_combinations:
            if per_channel and error_method == mct.QuantizationErrorMethod.KL:
                # we omit tests for per-channel with KL error method since it takes very long runtime
                continue
            qc = mct.QuantizationConfig(activation_error_method=mct.QuantizationErrorMethod.NOCLIPPING,
                                        weights_error_method=error_method,
                                        activation_quantization_method=mct.QuantizationMethod.POWER_OF_TWO,
                                        weights_quantization_method=quantize_method,
                                        activation_n_bits=16,
                                        weights_n_bits=8,
                                        relu_unbound_correction=False,
                                        weights_bias_correction=bias_correction,
                                        weights_per_channel_threshold=per_channel,
                                        input_scaling=input_scaling)
            q_model, quantization_info = mct.keras_post_training_quantization(model,
                                                                              representative_data_gen,
                                                                              n_iter=1,
                                                                              quant_config=qc,
                                                                              fw_info=DEFAULT_KERAS_INFO)

        model = model_gen()
        for quantize_method, error_method, relu_unbound_correction, shift_negative_correction\
                in activation_test_combinations:
            qc = mct.QuantizationConfig(activation_error_method=error_method,
                                        weights_error_method=mct.QuantizationErrorMethod.NOCLIPPING,
                                        activation_quantization_method=quantize_method,
                                        weights_quantization_method=mct.QuantizationMethod.POWER_OF_TWO,
                                        activation_n_bits=8,
                                        weights_n_bits=16,
                                        relu_unbound_correction=relu_unbound_correction,
                                        weights_bias_correction=False,
                                        weights_per_channel_threshold=False,
                                        shift_negative_activation_correction=shift_negative_correction)
            q_model, quantization_info = mct.keras_post_training_quantization(model,
                                                                              representative_data_gen,
                                                                              n_iter=1,
                                                                              quant_config=qc,
                                                                              fw_info=DEFAULT_KERAS_INFO)


if __name__ == '__main__':
    unittest.main()
