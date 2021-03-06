"""Test a ODEnet on the MNIST dataset with adversarial examples over multiple end times"""
# %%
from functools import partial

import torch
from torch import nn
import numpy as np
from sacred import Experiment
from pytorch_utils.sacred_utils import get_model_path, read_config, import_source
from visdom_observer.visdom_observer import VisdomObserver
from sacred.observers import FileStorageObserver

from training_functions import validate
import adversarial as adv


# %%
ATTACKS = {
    'fgsm':adv.fgsm
}

# %%
ex = Experiment('odenet-adv-mnist_time')
SAVE_DIR = 'runs/ODEnet-adversarial-test-mnist'
ex.observers.append(FileStorageObserver.create(SAVE_DIR))
ex.observers.append(VisdomObserver())

@ex.config
def input_config():
    """Parameters for sampling using the given model"""
    run_dir = 'runs/ODEnetSkipStepMnist/4'  #'runs/ODEMnistClassification/17'
    epoch = 15  #'latest'
    device = 'cpu'
    epsilon = 0.3 # epsilon for attack
    attack = 'fgsm' # type of attack, currently: [fgsm]
    end_time_start = 0.01
    end_time_end = 10 #1000
    num_times = 10 #1000
    tol = 1e-3
    batches = -1

class TruncIterator():
    def __init__(self, iterator, stop):
        self.iterator = iterator
        self.stop = stop

    def __iter__(self):
        end = self.stop if self.stop != -1 else len(self.iterator)
        it = iter(self.iterator)
        for i in range(end):
            yield next(it)

    def __len__(self):
        return self.stop if self.stop != -1 else len(self.iterator)

@ex.automain
def main(run_dir,
         epoch,
         device,
         attack,
         epsilon,
         end_time_start,
         end_time_end,
         num_times,
         tol,
         batches,
         _log):

    config = read_config(run_dir)
    _log.info(f"Read config from {run_dir}")

    model_ing = import_source(run_dir, "model_ingredient")
    model = model_ing.make_model(**{**config['model'], 'device':device}, _log=_log)
    path = get_model_path(run_dir, epoch)
    if isinstance(model, nn.DataParallel):
        model.module.load_state_dict(torch.load(path))
    else:
        model.load_state_dict(torch.load(path, map_location=device))
    model = model.eval()
    _log.info(f"Loaded state dict from {path}")

    if hasattr(model, "odeblock"):
        model.odeblock.atol = tol
        model.odeblock.rtol = tol

    data_ing = import_source(run_dir, "data_ingredient")
    dset, tl, vl, test_loader = data_ing.make_dataloaders(**{**config['dataset'],
                                                             'device':device},
                                                          _log=_log)

    attack = partial(ATTACKS[attack], epsilon=epsilon)
    adv_test_loader = adv.AdversarialLoader(model, test_loader, attack)
    adv_test_loader = TruncIterator(adv_test_loader, batches)
    _log.info("Testing model...")

    for end_time in np.linspace(end_time_start, end_time_end, num_times):
        model.odeblock.min_end_time = end_time
        model.odeblock.max_end_time = end_time
        model.odeblock.t = torch.tensor([0, end_time]).float()
        test_loss, test_acc = validate(model, adv_test_loader)
        ex.log_scalar("test_loss", test_loss)
        ex.log_scalar("test_acc", test_acc)
        ex.log_scalar("end_time", end_time)
        _log.info(f"end_time={end_time:.6f}, Test loss = {test_loss:.6f}, Test accuracy = {test_acc:.4f}")
