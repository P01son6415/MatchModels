"""An implementation of Matching Layer."""
import typing

from keras import backend as K
from keras.engine import Layer


class MatchingLayer(Layer):
    """
    Layer that computes a matching matrix between samples in two tensors.
    :param normalize: Whether to L2-normalize samples along the
        dot product axis before taking the dot product.
        If set to True, then the output of the dot product
        is the cosine proximity between the two samples.
    :param matching_type: the similarity function for matching
    :param kwargs: Standard layer keyword arguments.
    Examples:
        >>> import matchzoo as mz
        >>> layer = mz.layers.MatchingLayer(matching_type='dot',
        ...                                 normalize=True)
        >>> num_batch, left_len, right_len, num_dim = 5, 3, 2, 10
        >>> layer.build([[num_batch, left_len, num_dim],
        ...              [num_batch, right_len, num_dim]])
    """

    def __init__(self, normalize: bool = False,
                 matching_type: str = 'dot', **kwargs):
        """:class:`MatchingLayer` constructor."""
        super().__init__(**kwargs)
        self._normalize = normalize
        self._validate_matching_type(matching_type)
        self._matching_type = matching_type
        self._shape1 = None
        self._shape2 = None

    @classmethod
    def _validate_matching_type(cls, matching_type: str = 'dot'):
        valid_matching_type = ['dot', 'mul', 'plus', 'minus', 'concat']
        if matching_type not in valid_matching_type:
            raise ValueError(f"{matching_type} is not a valid matching type, "
                             f"{valid_matching_type} expected.")

    def build(self, input_shape: list):
        """
        Build the layer.
        :param input_shape: the shapes of the input tensors,
            for MatchingLayer we need tow input tensors.
        """
        # Used purely for shape validation.
        if not isinstance(input_shape, list) or len(input_shape) != 2:
            raise ValueError('A `MatchingLayer` layer should be called '
                             'on a list of 2 inputs.')
        self._shape1 = input_shape[0]
        self._shape2 = input_shape[1]
        for idx in 0, 2:
            if self._shape1[idx] != self._shape2[idx]:
                raise ValueError(
                    'Incompatible dimensions: '
                    f'{self._shape1[idx]} != {self._shape2[idx]}.'
                    f'Layer shapes: {self._shape1}, {self._shape2}.'
                )

    def call(self, inputs: list, **kwargs) -> typing.Any:
        """
        The computation logic of MatchingLayer.
        :param inputs: two input tensors.
        """
        x1 = inputs[0]
        x2 = inputs[1]
        if self._matching_type == 'dot':
            if self._normalize:
                x1 = K.l2_normalize(x1, axis=2)
                x2 = K.l2_normalize(x2, axis=2)
            return K.tf.expand_dims(K.tf.einsum('abd,acd->abc', x1, x2), 3)
        else:
            if self._matching_type == 'mul':
                def func(x, y):
                    return x * y
            elif self._matching_type == 'plus':
                def func(x, y):
                    return x + y
            elif self._matching_type == 'minus':
                def func(x, y):
                    return x - y
            elif self._matching_type == 'concat':
                def func(x, y):
                    return K.tf.concat([x, y], axis=3)
            else:
                raise ValueError(f"Invalid matching type."
                                 f"{self._matching_type} received."
                                 f"Mut be in `dot`, `mul`, `plus`, "
                                 f"`minus` and `concat`.")
            x1_exp = K.tf.stack([x1] * self._shape2[1], 2)
            x2_exp = K.tf.stack([x2] * self._shape1[1], 1)
            return func(x1_exp, x2_exp)

    def compute_output_shape(self, input_shape: list) -> tuple:
        """
        Calculate the layer output shape.
        :param input_shape: the shapes of the input tensors,
            for MatchingLayer we need tow input tensors.
        """
        if not isinstance(input_shape, list) or len(input_shape) != 2:
            raise ValueError('A `MatchingLayer` layer should be called '
                             'on a list of 2 inputs.')
        shape1 = list(input_shape[0])
        shape2 = list(input_shape[1])
        if len(shape1) != 3 or len(shape2) != 3:
            raise ValueError('A `MatchingLayer` layer should be called '
                             'on 2 inputs with 3 dimensions.')
        if shape1[0] != shape2[0] or shape1[2] != shape2[2]:
            raise ValueError('A `MatchingLayer` layer should be called '
                             'on 2 inputs with same 0,2 dimensions.')

        if self._matching_type in ['mul', 'plus', 'minus']:
            return shape1[0], shape1[1], shape2[1], shape1[2]
        elif self._matching_type == 'dot':
            return shape1[0], shape1[1], shape2[1], 1
        elif self._matching_type == 'concat':
            return shape1[0], shape1[1], shape2[1], shape1[2] + shape2[2]
        else:
            raise ValueError(f"Invalid `matching_type`."
                             f"{self._matching_type} received."
                             f"Must be in `mul`, `plus`, `minus` "
                             f"`dot` and `concat`.")

    def get_config(self) -> dict:
        """Get the config dict of MatchingLayer."""
        config = {
            'normalize': self._normalize,
            'matching_type': self._matching_type,
        }
        base_config = super(MatchingLayer, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


queryInput = Input(shape=(30,600))

titleInput = Input(shape=(30,600))

conv_1d_left = Conv1D(128, 3, padding = 'same')(queryInput)
conv_1d_right = Conv1D(128, 3, padding = 'same')(titleInput)

matching_layer = MatchingLayer(matching_type='plus')
embed_cross = matching_layer([conv_1d_left, conv_1d_right])

embed_cross = Conv2D(16, [5, 5], padding = 'same', activation = 'relu')(embed_cross)
embed_cross = MaxPooling2D(pool_size= [2, 2])(embed_cross)

embed_cross = Conv2D(32, [5, 5], padding = 'same', activation = 'relu')(embed_cross)
embed_cross = MaxPooling2D(pool_size= [2, 2])(embed_cross)

embed_cross = Conv2D(64, [5, 5], padding = 'same', activation = 'relu')(embed_cross)
embed_cross = MaxPooling2D(pool_size= [2, 2])(embed_cross)


embed_flat = Flatten()(embed_cross)

x = Dense(256, activation='relu')(embed_flat)
x = Dense(64, activation='relu')(x)
x = Dense(1, activation='sigmoid')(x)

model_arc = Model(inputs=[queryInput,titleInput], outputs=x)
model_arc.compile(loss='binary_crossentropy', 
                optimizer='adam',
                metrics=[metrics.mae, metrics.binary_accuracy])

