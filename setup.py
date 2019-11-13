# coding: utf-8
# create by tongshiwei on 2019/6/25

from setuptools import setup

setup(
    name='XKT',
    version='0.0.1',
    install_requires=[
        'tqdm',
        'mxnet',
        'gluonnlp',
        'sklearn',
        'longling>=1.3.0',
    ],  # And any other dependencies foo needs
    entry_points={
        "console_scripts": [
            "DKT = XKT.DKT.DKT:main",
            "DKTVMN = XKT.DKVMN.DKVMN:main"
        ],
    },
)
