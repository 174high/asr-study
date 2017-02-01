import ast

class HParams(object):
  """Creates an object for passing around hyperparameter values.
  Use the parse method to overwrite the default hyperparameters with values
  passed in as a string representation of a Python dictionary mapping
  hyperparameters to values.

  # Example
      hparams = magenta.common.HParams(batch_size=128, hidden_size=256)
      hparams.parse('{"hidden_size":512}')
      assert hparams.batch_size == 128
      assert hparams.hidden_size == 512
  """

  def __init__(self, from_str=None, **init_hparams):
    object.__setattr__(self, 'keyvals', init_hparams)

    if from_str:
        self.parse(from_str)

  def __getattr__(self, key):
    """Returns value of the given hyperameter, or None if does not exist."""
    return self.keyvals.get(key)

  def __setattr__(self, key, value):
    """Sets value for the hyperameter."""
    self.keyvals[key] = value

  def update(self, values_dict):
    """Merges in new hyperparameters, replacing existing with same key."""
    self.keyvals.update(values_dict)

  def parse(self, values_string):
    """Merges in new hyperparameters, replacing existing with same key."""
    self.update(ast.literal_eval(values_string))

    return self

  def values(self):
    """Return the hyperparameter values as a Python dictionary."""
    return self.keyvals
