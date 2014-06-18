__author__ = 'ryanplyler'

def sayhi(config):
    error = None

    try:
        server_output = "Executing action 'sayhi()'"
        response = "HI THERE!"

    except:
        error = 1

    return server_output, response, error
