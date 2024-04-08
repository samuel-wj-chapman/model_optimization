# Copyright 2021 Sony Semiconductor Israel, Inc. All rights reserved.
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


from typing import Callable, Any, List, Tuple, Union, Dict

import numpy as np

from model_compression_toolkit.core.common.quantization.quantization_fn_selection import get_weights_quantization_fn
from model_compression_toolkit.logger import Logger
from model_compression_toolkit.core.common.quantization.quantization_params_fn_selection import \
    get_activation_quantization_params_fn, get_weights_quantization_params_fn

from model_compression_toolkit.core.common.quantization.quantization_config import QuantizationConfig, \
    QuantizationErrorMethod
from model_compression_toolkit.target_platform_capabilities.target_platform import OpQuantizationConfig, \
    AttributeQuantizationConfig


##########################################
# Every node holds a quantization configuration
# for its weights and activations quantization, and a different quantization
# configuration for its activation quantization configuration.
##########################################


class BaseNodeQuantizationConfig(object):
    """
    Base class for node quantization configuration
    """

    def set_quant_config_attr(self, config_parameter_name: str, config_parameter_value: Any,
                              *args: List[Any], **kwargs: Dict[str, Any]):
        """
        Changes a BaseNodeQuantizationConfig's parameter.
        Note that arg and kwargs are only to allow clean override in the child classes.

        Args:
            config_parameter_name: parameter name to change.
            config_parameter_value: parameter value to change.
            args: A list of additional arguments.
            kwargs: A dictionary with additional key arguments.

        """

        if hasattr(self, config_parameter_name):
            setattr(self, config_parameter_name, config_parameter_value)
        else:
            Logger.warning(f"Parameter {config_parameter_name} could not be found in the node quantization config and "
                           f"was not updated!")

    def __repr__(self) -> str:
        """
        Returns: String to display a NodeQuantizationConfig object.
        """
        repr_str = ''
        for k, v in self.__dict__.items():
            repr_str += f'{k}: {v}\n'
        return repr_str


class NodeActivationQuantizationConfig(BaseNodeQuantizationConfig):
    """
    Attributes for configuring the quantization of the activations of a node.
    """
    def __init__(self,
                 qc: QuantizationConfig,
                 op_cfg: OpQuantizationConfig,
                 activation_quantization_fn: Callable,
                 activation_quantization_params_fn: Callable
                 ):
        """

        Args:
            qc: QuantizationConfig to create the node's config from.
            op_cfg: OpQuantizationConfig of the node with quantizers types to use when creating node quantization configuration.
            activation_quantization_fn: Function to use when quantizing the node's activations.
            activation_quantization_params_fn: Function to use when computing the threshold for quantizing a node's activations.
        """

        self.activation_quantization_fn = activation_quantization_fn
        self.activation_quantization_params_fn = activation_quantization_params_fn
        self.activation_quantization_params = {}
        self.activation_quantization_method = op_cfg.activation_quantization_method
        self.activation_error_method = qc.activation_error_method
        self.activation_n_bits = op_cfg.activation_n_bits
        self.relu_bound_to_power_of_2 = qc.relu_bound_to_power_of_2
        self.enable_activation_quantization = op_cfg.enable_activation_quantization
        self.activation_channel_equalization = qc.activation_channel_equalization
        self.input_scaling = qc.input_scaling
        self.min_threshold = qc.min_threshold
        self.l_p_value = qc.l_p_value
        self.shift_negative_activation_correction = qc.shift_negative_activation_correction
        self.z_threshold = qc.z_threshold
        self.shift_negative_ratio = qc.shift_negative_ratio
        self.shift_negative_threshold_recalculation = qc.shift_negative_threshold_recalculation

    def quantize_node_output(self,
                             tensors: Any) -> Any:
        """

        Args:
            tensors: framework tensor/s

        Returns:
            Framework tensor/s after applying fake quantization.

        """
        fake_quant = self.activation_quantization_fn(self.activation_n_bits,
                                                     self.activation_quantization_params)

        if fake_quant is None:
            Logger.critical(
                "Layer is intended to be quantized, but the fake_quant function is None.")  # pragma: no cover

        return fake_quant(tensors)

    @property
    def activation_error_method(self) -> QuantizationErrorMethod:
        """
        activation_error_method getter.
        """
        return self._activation_error_method

    @activation_error_method.setter
    def activation_error_method(self, value: QuantizationErrorMethod):
        """
        activation_error_method setter.

        Args:
            value: New activation_error_method to set to the node activation configuration.

        """
        self._activation_error_method = value
        self.activation_quantization_params_fn = get_activation_quantization_params_fn(activation_quantization_method=self.activation_quantization_method)

    def set_activation_quantization_fn(self, activation_quantization_fn: Callable):
        """
        Sets activation quantization function for the node.

        Args:
            activation_quantization_fn: Function for quantazing the activations.

        """
        self.activation_quantization_fn = activation_quantization_fn

    def set_activation_quantization_params_fn(self, activation_quantization_params_fn:Callable):
        """
        Sets activation params function for the node.

        Args:
            activation_quantization_params_fn: Function for calculating activation params.

        """
        self.activation_quantization_params_fn = activation_quantization_params_fn

    def set_activation_quantization_param(self,
                                          activation_params: dict):
        """
         Set a quantization parameter for the node's activation.

        Args:
            activation_params: Dictionary that contains weight quantization params.

        """
        assert self.enable_activation_quantization
        for param_name, param_value in activation_params.items():
            self.activation_quantization_params[param_name] = param_value

    def has_activation_quantization_params(self) -> bool:
        """

        Returns: Whether NodeQuantizationConfig has a activation quantization params or not.

        """
        return len(self.activation_quantization_params) > 0

    def no_quantization(self) -> bool:
        """
        Returns: Whether NodeQuantizationConfig does not have activation params.
        """
        return (not self.has_activation_quantization_params())

    def __eq__(self, other: Any) -> bool:
        """
        Compares the object to another object to find if they are equal.

        Args:
            other: An object to compare to.

        Returns: Whether the objects are identical or not.

        """
        if not isinstance(other, NodeActivationQuantizationConfig):
            return False

        return self.activation_quantization_fn == other.activation_quantization_fn and \
               self.activation_quantization_params_fn == other.activation_quantization_params_fn and \
               self.activation_error_method == other.activation_error_method and \
               self.activation_quantization_method == other.activation_quantization_method and \
               self.activation_n_bits == other.activation_n_bits and \
               self.enable_activation_quantization == other.enable_activation_quantization and \
               self.activation_channel_equalization == other.activation_channel_equalization and \
               self.input_scaling == other.input_scaling and \
               self.min_threshold == other.min_threshold and \
               self.l_p_value == other.l_p_value and \
               self.shift_negative_activation_correction == other.shift_negative_activation_correction and \
               self.z_threshold == other.z_threshold and \
               self.shift_negative_ratio == other.shift_negative_ratio and \
               self.shift_negative_threshold_recalculation == other.shift_negative_threshold_recalculation

    def __hash__(self):
        return hash((self.activation_quantization_fn,
                     self.activation_quantization_params_fn,
                     self.activation_error_method,
                     self.activation_quantization_method,
                     self.activation_n_bits,
                     self.enable_activation_quantization,
                     self.activation_channel_equalization,
                     self.input_scaling,
                     self.min_threshold,
                     self.l_p_value,
                     self.shift_negative_activation_correction,
                     self.z_threshold,
                     self.shift_negative_ratio,
                     self.shift_negative_threshold_recalculation))


class WeightsAttrQuantizationConfig:
    """
    Configuration for quantizing a weights attribute of a node.
    """
    def __init__(self,
                 qc: QuantizationConfig,
                 weights_attr_cfg: AttributeQuantizationConfig,
                 weights_channels_axis: Tuple[int, int] = None):
        """

        Args:
            qc: QuantizationConfig to create the node's config from.
            weights_attr_cfg: AttributeQuantizationConfig with parameters to use when creating the node's attribute quantization config.
            weights_channels_axis: Axis to quantize a node's attribute when quantizing per-channel (if not quantizing per-channel than expecting None).
        """
        self.weights_quantization_fn = get_weights_quantization_fn(weights_attr_cfg.weights_quantization_method)
        self.weights_quantization_params_fn = get_weights_quantization_params_fn(weights_attr_cfg.weights_quantization_method)
        self.weights_channels_axis = weights_channels_axis
        self.weights_quantization_params = {}
        self.weights_quantization_method = weights_attr_cfg.weights_quantization_method
        self.weights_error_method = qc.weights_error_method
        self.weights_n_bits = weights_attr_cfg.weights_n_bits
        self.weights_per_channel_threshold = weights_attr_cfg.weights_per_channel_threshold
        self.enable_weights_quantization = weights_attr_cfg.enable_weights_quantization
        self.l_p_value = qc.l_p_value



    @property
    def weights_error_method(self) -> QuantizationErrorMethod:
        """
        weights_error_method getter.
        """
        return self._weights_error_method

    @weights_error_method.setter
    def weights_error_method(self, value: QuantizationErrorMethod):
        """
        weights_error_method setter.

        Args:
            value: New weights_error_method to set to the node weights configuration.

        """
        self._weights_error_method = value
        self.weights_quantization_params_fn = get_weights_quantization_params_fn(weights_quantization_method=self.weights_quantization_method)

    def set_weights_quantization_fn(self, weights_quantization_fn: Callable):
        """
        Sets weights quantization function for the node.

        Args:
            weights_quantization_fn: Function for quantazing the weights.

        """
        self.weights_quantization_fn = weights_quantization_fn

    def set_weights_quantization_params_fn(self, weights_quantization_params_fn: Callable):
        """
        Sets weights params function for the node.

        Args:
            weights_quantization_params_fn: Function for calculating the weights params.

        """
        self.weights_quantization_params_fn = weights_quantization_params_fn

    def set_weights_quantization_param(self,
                                       weights_params: dict):
        """
         Set a quantization parameter for the node's weights.

        Args:
            weights_params: Dictionary that contains weight quantization params.

        """
        assert self.enable_weights_quantization
        for param_name, param_value in weights_params.items():
            self.weights_quantization_params[param_name] = param_value

    def calculate_and_set_weights_params(self, tensor_data: np.ndarray, min_threshold: float):
        """
        Args:
            tensor_data: Tensor content as Numpy array.
            min_threshold: A minimal threshold to set as quantization parameter.

        Returns:
            Recalculated weights quantization params from the kernel and channel axis.

        """
        assert self.enable_weights_quantization
        if self.weights_quantization_params_fn is not None:
            self.set_weights_quantization_param(self.weights_quantization_params_fn(tensor_data,
                                                                                    p=self.l_p_value,
                                                                                    n_bits=self.weights_n_bits,
                                                                                    per_channel=self.weights_per_channel_threshold and self.weights_channels_axis is not None,
                                                                                    channel_axis=self.weights_channels_axis[0],  # output channel axis
                                                                                    min_threshold=min_threshold))
        else:
            self.set_weights_quantization_param({})

    def has_weights_quantization_params(self) -> bool:
        """

        Returns: Whether NodeQuantizationConfig has weights quantization params or not.

        """
        return len(self.weights_quantization_params) > 0

    def __eq__(self, other: Any) -> bool:
        """
        Compares the object to another object to find if they are equal.

        Args:
            other: An object to compare to.

        Returns: Whether the objects are identical or not.

        """
        if not isinstance(other, WeightsAttrQuantizationConfig):
            return False

        return self.weights_quantization_fn == other.weights_quantization_fn and \
               self.weights_quantization_params_fn == other.weights_quantization_params_fn and \
               self.weights_channels_axis == other.weights_channels_axis and \
               self.weights_error_method == other.weights_error_method and \
               self.weights_quantization_method == other.weights_quantization_method and \
               self.weights_n_bits == other.weights_n_bits and \
               self.weights_per_channel_threshold == other.weights_per_channel_threshold and \
               self.enable_weights_quantization == other.enable_weights_quantization and \
               self.l_p_value == other.l_p_value

    def __hash__(self):
        return hash((self.weights_quantization_fn,
                     self.weights_quantization_params_fn,
                     self.weights_channels_axis,
                     self.weights_error_method,
                     self.weights_quantization_method,
                     self.weights_n_bits,
                     self.weights_per_channel_threshold,
                     self.enable_weights_quantization,
                     self.l_p_value))


class NodeWeightsQuantizationConfig(BaseNodeQuantizationConfig):
    """
    Holding a mapping between the node's weights attributes and their quantization configurations,
    in addition to quantization parameters that are global for all attributes of the represented node.
    """
    def __init__(self, qc: QuantizationConfig,
                 op_cfg: OpQuantizationConfig,
                 weights_channels_axis: Tuple[int, int],
                 node_attrs_list: List[str]):
        """

        Args:
            qc: QuantizationConfig to create the node's config from.
            op_cfg: OpQuantizationConfig of the node with quantizers types to use when creating node quantization configuration.
            weights_channels_axis: Axis to quantize a node's weights attribute when quantizing per-channel.
            node_attrs_list: A list of the node's weights attributes names.

        """
        self.min_threshold = qc.min_threshold
        self.simd_size = op_cfg.simd_size
        self.weights_second_moment_correction = qc.weights_second_moment_correction
        self.weights_bias_correction = qc.weights_bias_correction

        # Initialize a quantization configuration for each of the node's attributes
        self.attributes_config_mapping = {}
        self.pos_attributes_config_mapping = {}
        for attr in node_attrs_list:
            if isinstance(attr, int):
                # this is a positional attribute, so it needs to be handled separately.
                # we assume that a positional attribute is quantized with the default configuration provided in the TPC.
                if op_cfg.default_weight_attr_config.enable_weights_quantization:
                    Logger.critical(f"Quantizing constant weights is not supported.")
                self.pos_attributes_config_mapping[attr] = WeightsAttrQuantizationConfig(qc=qc,
                                                                                         weights_attr_cfg=op_cfg.default_weight_attr_config,
                                                                                         weights_channels_axis=weights_channels_axis)
            else:
                # In Tensorflow, the attribute name is composed of the framework attribute name and the layer name,
                # therefore, we need to look for the attribute in the op_cfg that is contained in the node attribute's name.
                attrs_included_in_name = {k: v for k, v in op_cfg.attr_weights_configs_mapping.items() if k in attr}
                if len(attrs_included_in_name) > 1:
                    Logger.error(f"Found multiple attribute in TPC OpConfig that are contained "
                                 f"in the attribute name '{attr}'."
                                 f"Please fix the TPC attribute names mapping such that each operator's attribute would "
                                 f"have a unique matching name.")
                if len(attrs_included_in_name) == 0:
                    attr_cfg = op_cfg.default_weight_attr_config
                else:
                    attr_cfg = list(attrs_included_in_name.values())[0]

                self.attributes_config_mapping[attr] = WeightsAttrQuantizationConfig(qc=qc,
                                                                                     weights_attr_cfg=attr_cfg,
                                                                                     weights_channels_axis=weights_channels_axis)

    def get_attr_config(self, attr_name: Union[str, int]) -> WeightsAttrQuantizationConfig:
        """
        Returns a weights attribute config for an attribute that contains the given name.
        If multiple attributes that contain the given name are found - looking for the exact name, otherwise,
        fails with an error message.
        If none attributes that contain the given name are found - fails with an error message.

        Args:
            attr_name: The name of the attribute to get its quantization configuration.

        Returns: An attribute quantization configuration.

        """
        if attr_name is None:
            Logger.error("Got 'None' attribute name for retrieving weights attribute quantization configuration.")

        if isinstance(attr_name, int):
            # this is a positional attribute
            attr_cfg = self.pos_attributes_config_mapping.get(attr_name)
        else:
            attrs_with_name = self._extract_config_for_attributes_with_name(attr_name)
            attr_cfg = None
            if len(attrs_with_name) == 1:
                attr_cfg = [v for v in attrs_with_name.values()][0]
            elif len(attrs_with_name) > 1:
                Logger.warning(f"Found multiple weight attributes containing the name {attr_name}: "
                               f"{list(attrs_with_name.keys())}. Looking for an attributes with the exact name.")
                # If no attribute with the exact name then an error would be thrown
                attr_cfg = self.attributes_config_mapping.get(attr_name)

        if attr_cfg is None:
            Logger.error(f"Weight attribute '{attr_name}' config could not be found.")

        return attr_cfg

    def set_attr_config(self, attr_name: Union[str, int], attr_qc: WeightsAttrQuantizationConfig):
        """
        Adding a new attribute with quantization configuration to the node's weights configurations mapping.

        Args:
            attr_name: The name of the attribute to set a quantization configuration to.
            attr_qc: The quantization configuration to set.

        """
        if isinstance(attr_name, int):
            self.pos_attributes_config_mapping[attr_name] = attr_qc
        else:
            self.attributes_config_mapping[attr_name] = attr_qc

    def has_attribute_config(self, attr_name: Union[str, int]) -> bool:
        """
        Checks whether the node weights configuration contains a configuration for a given weights attribute.

        Args:
            attr_name: The attribute name to check if a quantization configuration is defined for.

        Returns: True if the attribute exists in the attributes configuration mapping, False otherwise.

        """
        if isinstance(attr_name, int):
            return self.pos_attributes_config_mapping.get(attr_name, False)
        else:
            saved_attr_name = self._extract_config_for_attributes_with_name(attr_name)
            if len(saved_attr_name) >= 1:
                return True

        return False

    def _extract_config_for_attributes_with_name(self, attr_name) -> Dict[str, WeightsAttrQuantizationConfig]:
        """
        Extract the saved attributes that contain the given attribute name.
        Relevant to Tensorflow where attributes are presented with the layer name and index,
        in addition to the attribute actual name.

        Args:
            attr_name: An attribute to extract its saved name.

        Returns: A mapping between attributes that contain the given name to their configuration.

        """
        attrs_with_name = {k: v for k, v in self.attributes_config_mapping.items() if attr_name in k}
        if len(attrs_with_name) > 1:
            Logger.warning(f"Found multiple weight attributes containing the name {attr_name}: "
                           f"{list(attrs_with_name.keys())}.")
        return attrs_with_name

    def set_quant_config_attr(self, config_parameter_name: str, config_parameter_value: Any, attr_name: str = None,
                              *args: List[Any], **kwargs: Dict[str, Any]):
        """
        This method overrides the parent class set_quant_config_attr to enable setting a specific weights
        attribute config parameter.

        Args:
            attr_name: attribute name to change.
            config_parameter_name: parameter name to change.
            config_parameter_value: parameter value to change.
            args: A list of additional arguments.
            kwargs: A dictionary with additional key arguments.

        """

        if attr_name is None:
            super(NodeWeightsQuantizationConfig, self).set_quant_config_attr(config_parameter_name,
                                                                             config_parameter_value,
                                                                             *args, **kwargs)
        else:
            if self.has_attribute_config(attr_name):
                attr_cfg = self.get_attr_config(attr_name)
                if hasattr(attr_cfg, config_parameter_name):
                    setattr(attr_cfg, config_parameter_name, config_parameter_value)
                else:
                    Logger.warning(f"Parameter {config_parameter_name} could not be found in the node quantization config of "
                                   f"weights attribute {attr_name} and was not updated!")
            else:
                Logger.error(f"Weights attribute {attr_name} could not be found to set parameter {config_parameter_name}.")

    def __eq__(self, other: Any) -> bool:
        """
        Compares the object to another object to find if they are equal.

        Args:
            other: An object to compare to.

        Returns: Whether the objects are identical or not.

        """
        if not isinstance(other, NodeWeightsQuantizationConfig):
            return False

        return self.min_threshold == other.min_threshold and \
            self.simd_size == other.simd_size and \
            self.weights_second_moment_correction == other.weights_second_moment_correction and \
            self.weights_bias_correction == other.weights_bias_correction and \
            self.attributes_config_mapping.keys() == other.attributes_config_mapping.keys() and \
            all([self.attributes_config_mapping[k] == other.attributes_config_mapping[k]
                 for k in self.attributes_config_mapping.keys()]) and \
            self.pos_attributes_config_mapping.keys() == other.pos_attributes_config_mapping.keys() and \
            all([self.pos_attributes_config_mapping[k] == other.pos_attributes_config_mapping[k]
                 for k in self.pos_attributes_config_mapping.keys()])

    def __hash__(self):
        return hash((self.min_threshold,
                     self.simd_size,
                     self.weights_second_moment_correction,
                     self.weights_bias_correction,
                     frozenset(self.attributes_config_mapping),
                     frozenset(self.pos_attributes_config_mapping)))
