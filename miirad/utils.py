from functools import partial

def caller(*args):
    for c in args:
        c()

def partial_caller(*args):
    return partial(caller, *args)
