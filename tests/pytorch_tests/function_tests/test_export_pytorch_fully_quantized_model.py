# Copyright 2022 Sony Semiconductor Israel, Inc. All rights reserved.
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
import os
import struct
import tempfile
import unittest

import numpy as np
import torch
from torchvision.models.mobilenetv2 import mobilenet_v2
import model_compression_toolkit as mct
from model_compression_toolkit.core.common.constants import FOUND_ONNX
from model_compression_toolkit.core.pytorch.utils import to_torch_tensor
from model_compression_toolkit.exporter.model_exporter import pytorch_export_model, PyTorchExportMode

_, SAVED_MODEL_PATH_PTH = tempfile.mkstemp('.pth')
_, SAVED_MODEL_PATH_ONNX = tempfile.mkstemp('.onnx')

if FOUND_ONNX:
    import onnx
    class TestPyTorchFakeQuantExporter(unittest.TestCase):

        def tearDown(self):
            os.remove(SAVED_MODEL_PATH_PTH)
            os.remove(SAVED_MODEL_PATH_ONNX)

        def repr_datagen(self):
            for _ in range(1):
                yield [np.random.random((1, 3, 224, 224))]

        def setUp(self) -> None:
            self.model = mobilenet_v2(pretrained=True)
            self.exportable_model = self.run_mct(self.model, new_experimental_exporter=True)
            self.exportable_model.eval()
            pytorch_export_model(model=self.exportable_model,
                                 is_layer_exportable_fn=lambda x: x,
                                 mode=PyTorchExportMode.FAKELY_QUANT_TORCHSCRIPT,
                                 save_model_path=SAVED_MODEL_PATH_PTH,
                                 repr_dataset=self.repr_datagen)
            self.exported_model_pth = torch.load(SAVED_MODEL_PATH_PTH)
            self.exported_model_pth.eval()
            pytorch_export_model(model=self.exportable_model,
                                                           is_layer_exportable_fn=lambda x: x,
                                                           mode=PyTorchExportMode.FAKELY_QUANT_ONNX,
                                                           save_model_path=SAVED_MODEL_PATH_ONNX,
                                                           repr_dataset=self.repr_datagen)
            self.exported_model_onnx = onnx.load(SAVED_MODEL_PATH_ONNX)
            # Check that the model is well formed
            onnx.checker.check_model(self.exported_model_onnx)

        def run_mct(self, model, new_experimental_exporter):
            core_config = mct.CoreConfig()

            new_export_model, _ = mct.pytorch_post_training_quantization_experimental(
                in_module=model,
                core_config=core_config,
                representative_data_gen=self.repr_datagen,
                new_experimental_exporter=new_experimental_exporter)
            return new_export_model

        def test_pth_predictions(self):
            images = to_torch_tensor(next(self.repr_datagen()))[0]
            diff = self.exported_model_pth(images) - self.exportable_model(images)
            max_abs_error = np.max(np.abs(diff.cpu().detach().numpy()))
            print(f'Max abs error: {max_abs_error}')
            self.assertTrue(max_abs_error == 0)

        def test_onnx_weights(self):

            # Get Kernel from pth exported file
            layer_kernel = self.exported_model_pth.features_2_conv_0_0_bn.layer.weight
            layer_kernel_shape = layer_kernel.shape

            # Get bias from pth exported file
            layer_bias = self.exported_model_pth.features_2_conv_0_0_bn.layer.bias
            layer_bias_shape = layer_bias.shape

            # Assert correct weights indices that we check
            self.assertTrue(self.exported_model_onnx.graph.initializer[6].name=='features_2_conv_0_0_bn.layer.weight')
            self.assertTrue(self.exported_model_onnx.graph.initializer[7].name == 'features_2_conv_0_0_bn.layer.bias')

            # Get Kernel from onnx exported file
            # In the protobuf - initializer 6 is features_2_conv_0_0_bn's kernel. We parse and reshape it.
            kernel_float_onnx = np.array(struct.unpack(int(len(self.exported_model_onnx.graph.initializer[6].raw_data) / 4) * 'f',
                                         self.exported_model_onnx.graph.initializer[6].raw_data))
            kernel_float_onnx_reshaped = kernel_float_onnx.reshape(layer_kernel_shape)

            # Assert the kernel is equal in two models
            kernels_diff = layer_kernel.cpu().detach().numpy()-kernel_float_onnx_reshaped
            max_abs_error = np.max(np.abs(kernels_diff))
            self.assertTrue(max_abs_error == 0)

            # Get bias from onnx exported file
            # In the protobuf - initializer 7 is features_2_conv_0_0_bn's bias. We parse and reshape it.
            bias_float_onnx = np.array(struct.unpack(int(len(self.exported_model_onnx.graph.initializer[7].raw_data) / 4) * 'f',
                                         self.exported_model_onnx.graph.initializer[7].raw_data))
            bias_float_onnx_reshaped = bias_float_onnx.reshape(layer_bias_shape)

            # Assert the kernel is equal in two models
            bias_diff = layer_bias.cpu().detach().numpy()-bias_float_onnx_reshaped
            max_abs_error = np.max(np.abs(bias_diff))
            self.assertTrue(max_abs_error == 0)