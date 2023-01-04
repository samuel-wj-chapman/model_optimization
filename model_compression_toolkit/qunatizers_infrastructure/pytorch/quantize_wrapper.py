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
# ==============================================================================f
from typing import List, Union
from model_compression_toolkit.core.common.constants import FOUND_TORCH
from model_compression_toolkit.core.common.logger import Logger
from model_compression_toolkit.qunatizers_infrastructure.common.node_quantization_dispatcher import \
    NodeQuantizationDispatcher

if FOUND_TORCH:
    import torch
    import torch.nn as nn

    DISPATCHER = "dispatcher"
    LAYER = "layer"
    STEPS = "optimizer_step"
    TRAINING = "training"


    class PytorchQuantizationWrapper(nn.Module):
        def __init__(self,
                     module: nn.Module,
                     dispatcher: NodeQuantizationDispatcher):
            """
            Pytorch Quantization Wrapper takes a pytorch module and dispatcher and infer a quantized module.

            Args:
                module: A pytorch module.
                dispatcher: A node quantization dispatcher.
            """
            super().__init__()
            self.dispatcher = dispatcher
            self.add_module('layer', module)
            self._weight_vars = []

            # Init weights quantizers
            for name, quantizer in self.dispatcher.weight_quantizers.items():
                weight = getattr(self.layer, name)
                quantizer.initialize_quantization(weight.shape, name, self)
                self._weight_vars.append((name, weight, quantizer))

            # Init activations quantizers
            self._activation_vars = []
            for i,quantizer in enumerate(self.dispatcher.activation_quantizers):
                quantizer.initialize_quantization(None, "tensor"+str(i), self.layer)
                self._activation_vars.append(quantizer)


        def set_quantize_weights(self, quantized_weights: dict):
            """
            This function updates layer weights after quantization.

            Args:
                quantized_weights: a dict of weight to update

            Returns: None

            """
            for weight_attr in self.dispatcher.weight_quantizers.keys():
                weight = quantized_weights.get(weight_attr)
                current_weight = getattr(self.layer, weight_attr)
                if current_weight.shape != weight.shape:
                    Logger.error(
                        f"Existing layer weight shape {current_weight.shape} is incompatible with provided weight shape {weight.shape}")  # pragma: no cover

                setattr(self.layer, weight_attr, torch.nn.Parameter(weight))

        def forward(self, x: torch.Tensor) -> Union[torch.Tensor, List[torch.Tensor]]:
            """
            PytorchQuantizationWrapper forward functions
            Args:
                x: layer's inputs

            Returns: a tensor that simulates a quantized layer.

            """

            # ----------------------------------
            # Quantize all weights, and replace them in the underlying layer.
            # ----------------------------------
            quantized_weights = {}
            for name, unquantized_weight, quantizer in self._weight_vars:
                quantized_weight = quantizer(unquantized_weight, self.training)
                quantized_weights.update({name: quantized_weight})

            self.set_quantize_weights(quantized_weights)

            # ----------------------------------
            # Layer operation
            # ----------------------------------
            outputs = self.layer(x)

            # ----------------------------------
            # Quantize all activations
            # ----------------------------------
            if self.dispatcher.is_activation_quantization:

                if not isinstance(outputs, list):
                    outputs = [outputs]

                if len(outputs) != self.dispatcher.num_act_quantizers:
                    Logger.error(f"Number of outputs {len(outputs)} is incompatible number of activation quantizers {self.dispatcher.num_act_quantizers}")  # pragma: no cover

                # Quantize all activations tensors
                outputs_quantized = []
                for quantizer,output in zip(self._activation_vars,outputs):
                    outputs_quantized.append(quantizer(output))

                outputs = outputs_quantized[0] if len(outputs_quantized) == 1 else outputs_quantized

            return outputs

else:
    class PytorchQuantizationWrapper(object):
        def __init__(self, layer, dispatcher: NodeQuantizationDispatcher):
            """
            Pytorch Quantization Wrapper takes a pytorch module and dispatcher and infer a quantized layer.

            Args:
                layer: A pytorch module.
                dispatcher: A node quantization dispatcher.
            """
            Logger.critical('Installing Pytorch is mandatory '
                            'when using PytorchQuantizationWrapper. '
                            'Could not find torch package.')
