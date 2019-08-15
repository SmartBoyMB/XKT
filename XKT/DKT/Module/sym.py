# coding: utf-8
# Copyright @tongshiwei
"""
This file define the networks structure and
provide a simplest training and testing example.
"""

import logging
import os

import mxnet as mx
from longling.ML.MxnetHelper.toolkit.ctx import split_and_load
from longling.ML.MxnetHelper.toolkit.viz import plot_network, VizError
from mxnet import nd, autograd
from sklearn.metrics import roc_auc_score
from tqdm import tqdm

from XKT.shared import SLMLoss

# set parameters
try:
    # for python module
    from .etl import transform
    from .configuration import Configuration
    from .net import *
except (ImportError, SystemError):
    # for python script
    from etl import transform
    from configuration import Configuration
    from net import *

__all__ = ["get_net", "net_viz", "fit_f", "BP_LOSS_F", "eval_f"]


def get_net(ku_num, hidden_num, nettype="DKT", dropout=0.0, **kwargs):
    if nettype in {"EmbedDKT", "DKT"}:
        return DKTNet(ku_num, hidden_num, nettype, dropout, **kwargs)
    else:
        raise TypeError("Unknown nettype: %s" % nettype)


class Loss(SLMLoss):
    pass


def net_viz(_net, _cfg, view_tag=False, **kwargs):
    """visualization check, only support pure static network"""
    batch_size = _cfg.batch_size
    model_dir = _cfg.model_dir
    logger = kwargs.get(
        'logger',
        _cfg.logger if hasattr(_cfg, 'logger') else logging
    )

    try:
        viz_dir = os.path.join(model_dir, "plot/network")
        logger.info("visualization: file in %s" % viz_dir)
        from copy import deepcopy

        viz_net = deepcopy(_net)
        viz_net.length = 2
        viz_shape = {'data': (batch_size,) + (2,)}
        x = mx.sym.var("data")
        sym = viz_net(x)[1][-1]
        plot_network(
            nn_symbol=sym,
            save_path=viz_dir,
            shape=viz_shape,
            node_attrs={"fixedsize": "false"},
            view=view_tag
        )
    except VizError as e:
        logger.error("error happen in visualization, aborted")
        logger.error(e)


def get_data_iter(_cfg, ku_num):
    def pseudo_data_generation():
        # 在这里定义测试用伪数据流
        import random
        random.seed(10)

        raw_data = [
            [
                (random.randint(0, ku_num - 1), random.randint(-1, 1))
                for _ in range(random.randint(2, 20))
            ] for _ in range(1000)
        ]

        return raw_data

    return transform(pseudo_data_generation(), _cfg)


def fit_f(_net, _data, bp_loss_f, loss_function, loss_monitor):
    data, data_mask, label, pick_index, label_mask = _data
    output, _ = _net(data, data_mask)
    bp_loss = None
    for name, func in loss_function.items():
        loss = func(output, pick_index, label, label_mask)
        if name in bp_loss_f:
            bp_loss = loss
        loss_value = nd.mean(loss).asscalar()
        if loss_monitor:
            loss_monitor.update(name, loss_value)
    return bp_loss


def eval_f(_net, test_data, ctx=mx.cpu()):
    ground_truth = []
    prediction = []

    def evaluation_function(y_true, y_pred):
        return roc_auc_score(y_true, y_pred)

    for batch_data in tqdm(test_data, "evaluating"):
        ctx_data = split_and_load(
            ctx, *batch_data,
            even_split=False
        )
        for (data, data_mask, label, pick_index, label_mask) in ctx_data:
            output, _ = _net(data, data_mask)
            output = mx.nd.slice(output, (None, None), (None, -1))
            output = mx.nd.pick(output, pick_index)
            pred = output.asnumpy().tolist()
            label = label.asnumpy().tolist()
            for i, length in enumerate(label_mask.asnumpy().tolist()):
                length = int(length)
                ground_truth.extend(label[i][:length])
                prediction.extend(pred[i][:length])

    return {
        "auc": evaluation_function(ground_truth, prediction)
    }


BP_LOSS_F = Loss


def numerical_check(_net, _cfg, ku_num):
    net.initialize()

    datas = get_data_iter(_cfg, ku_num)

    bp_loss_f = {"SLMLoss": BP_LOSS_F(lw1=0.003)}
    loss_function = {}
    loss_function.update(bp_loss_f)
    from longling.ML.toolkit.monitor import MovingLoss
    from longling.ML.MxnetHelper.glue import module

    loss_monitor = MovingLoss(loss_function)

    # train check
    trainer = module.Module.get_trainer(
        _net, optimizer=_cfg.optimizer,
        optimizer_params=_cfg.optimizer_params,
        select=_cfg.train_select
    )

    for epoch in range(0, 100):
        for _data in tqdm(datas, "Epoch: %s" % epoch):
            with autograd.record():
                bp_loss = fit_f(
                    _net, _data, bp_loss_f, loss_function, loss_monitor
                )
            assert bp_loss is not None
            bp_loss.backward()
            trainer.step(1)
        print("epoch-%d: %s" % (epoch, list(loss_monitor.items())))

        if epoch % 1 == 0:
            print(eval_f(_net, datas))


if __name__ == '__main__':
    cfg = Configuration(dataset="junyi")

    # generate sym
    net = get_net(835, 900)

    # # visualiztion check
    # net_viz(net, cfg, False)

    # # numerical check
    numerical_check(net, cfg, 835)
