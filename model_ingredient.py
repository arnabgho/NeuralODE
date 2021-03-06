"""Ingredient for making a ODEnet model for MNIST"""

import torch
from torch import nn
from sacred import Ingredient
from modules import ODEnetRandTime,ODEnetSkipStep

model_ingredient = Ingredient('model')

@model_ingredient.config
def model_config():
    """Config for model"""
    in_channels = 1
    state_channels = 16
    state_size = 7
    output_size = 10
    act = 'relu'
    tol = 1e-3
    min_end_time = 1
    max_end_time = 10
    device = 'cpu'

@model_ingredient.capture
def make_model(in_channels,
               state_channels,
               state_size,
               output_size,
               act,
               tol,
               min_end_time,
               max_end_time,
               device,
               _log):
    """Create ODEnet model from config"""
    #ode_model = ODEnetRandTime(in_channels,
    ode_model = ODEnetSkipStep(in_channels,
                           state_channels,
                           state_size,
                           output_size=output_size,
                           act=act,
                           min_end_time=min_end_time,
                           max_end_time=max_end_time,
                           tol=tol)
    if isinstance(device, list):
        model = nn.DataParallel(ode_model, device_ids=device).to(device[0])
    else:
        model = ode_model.to(device)

    params = torch.nn.utils.parameters_to_vector(model.parameters())
    num_params = len(params)
    _log.info(f"Created ODEnetRandTime model with {num_params} parameters \
    on {device}")

    ode_params = torch.nn.utils.parameters_to_vector(
        ode_model.odefunc.parameters()).shape[0]
    _log.info(f"ODE function has {ode_params} parameters")
    return model
