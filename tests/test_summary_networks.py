# Copyright (c) 2022 The BayesFlow Developers

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import numpy as np
import pytest

from bayesflow.attention import InducedSelfAttentionBlock, SelfAttentionBlock
from bayesflow.summary_networks import DeepSet, SequentialNetwork, SetTransformer, TimeSeriesTransformer


def _gen_randomized_3d_data(low=1, high=32, dtype=np.float32):
    """Helper function to generate randomized 3d data for summary modules, min and
    max dimensions for each axis are given by ``low`` and ``high``."""

    # Randomize batch data
    x = (
        np.random.default_rng()
        .normal(
            size=(
                np.random.randint(low=low, high=high + 1),
                np.random.randint(low=low, high=high + 1),
                np.random.randint(low=low, high=high + 1),
            )
        )
        .astype(dtype)
    )

    # Random permutation along first axis
    perm = np.random.default_rng().permutation(x.shape[1])
    x_perm = x[:, perm, :]
    return x, x_perm, perm


@pytest.mark.parametrize("num_equiv", [1, 3])
@pytest.mark.parametrize("summary_dim", [13, 2])
def test_deep_set(num_equiv, summary_dim):
    """This function tests the fidelity of the ``DeepSet`` with a couple of relevant
    configurations w.r.t. permutation invariance and output dimensions."""

    # Prepare settings for the deep set
    settings = {"num_equiv": num_equiv, "summary_dim": summary_dim}
    inv_net = DeepSet(**settings)

    # Create input and permuted version with randomized shapes
    x, x_perm, _ = _gen_randomized_3d_data()

    # Pass unpermuted and permuted inputs
    out = inv_net(x).numpy()
    out_perm = inv_net(x_perm).numpy()

    # Assert numebr of equivariant layers correct
    assert len(inv_net.equiv_layers.layers) == num_equiv
    # Assert outputs equal
    assert np.allclose(out, out_perm, atol=1e-5)
    # Assert shape 2d
    assert len(out.shape) == 2 and len(out_perm.shape) == 2
    # Assert batch and last dimension equals output dimension
    assert x.shape[0] == out.shape[0] and x_perm.shape[0] == out.shape[0]
    assert out.shape[1] == summary_dim and out_perm.shape[1] == summary_dim


@pytest.mark.parametrize("num_conv_layers", [1, 3])
@pytest.mark.parametrize("lstm_units", [16, 32])
def test_sequential_network(num_conv_layers, lstm_units):
    """This function tests the fidelity of the ``SequentialNetwork`` w.r.t. output dimensions
    using a number of relevant configurations."""

    # Create settings dict and network
    settings = {
        "summary_dim": np.random.randint(low=1, high=32),
        "num_conv_layers": num_conv_layers,
        "lstm_units": lstm_units,
    }
    net = SequentialNetwork(**settings)

    # Create test data and pass through network
    x, _, _ = _gen_randomized_3d_data()
    out = net(x)

    # Test shape 2d
    assert len(out.shape) == 2
    # Test summary stats equal default
    assert out.shape[1] == settings["summary_dim"]
    # Test first dimension unaltered
    assert out.shape[0] == x.shape[0]


@pytest.mark.parametrize("summary_dim", [13, 4])
@pytest.mark.parametrize("num_seeds", [1, 3])
@pytest.mark.parametrize("num_attention_blocks", [1, 2])
@pytest.mark.parametrize("num_inducing_points", [None, 4])
def test_set_transformer(summary_dim, num_seeds, num_attention_blocks, num_inducing_points):
    """This function tests the fidelity of the ``SetTransformer`` with a couple of relevant
    configurations w.r.t. permutation invariance and output dimensions."""

    # Prepare settings for transformer
    att_dict = {"num_heads": 2, "key_dim": 16}
    dense_dict = {"units": 16, "activation": "relu"}

    # Create input and permuted version with randomized shapes
    x, x_perm, _ = _gen_randomized_3d_data()

    transformer = SetTransformer(
        input_dim=x.shape[2],
        attention_settings=att_dict,
        dense_settings=dense_dict,
        summary_dim=summary_dim,
        num_attention_blocks=num_attention_blocks,
        num_inducing_points=num_inducing_points,
        num_seeds=num_seeds,
    )

    # Pass unpermuted and permuted inputs
    out = transformer(x).numpy()
    out_perm = transformer(x_perm).numpy()

    # Assert numebr of equivariant layers correct
    assert len(transformer.attention_blocks.layers) == num_attention_blocks
    # Assert outputs equal
    assert np.allclose(out, out_perm, atol=1e-5)
    # Assert shape 2d
    assert len(out.shape) == 2 and len(out_perm.shape) == 2
    # Assert batch and last dimension equals output dimension
    assert x.shape[0] == out.shape[0] and x_perm.shape[0] == out.shape[0]
    out_dim = int(num_seeds * summary_dim)
    assert out.shape[1] == out_dim and out_perm.shape[1] == out_dim
    # Assert type of attention layer
    for block in transformer.attention_blocks.layers:
        if num_inducing_points is None:
            assert type(block) is SelfAttentionBlock
        else:
            assert type(block) is InducedSelfAttentionBlock
