import logging
import datetime

from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate as django_authenticate
from django.contrib.auth import login, REDIRECT_FIELD_NAME
from django_odesk.core.clients import DefaultClient
from django_odesk.auth import (
    ODESK_REDIRECT_SESSION_KEY,
    ODESK_TOKEN_SESSION_KEY,
    ENCRYPTION_KEY_NAME
)

from encrypt import encrypt_token


def authenticate(request):
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    request.session[ODESK_REDIRECT_SESSION_KEY] = redirect_to
    odesk_client = DefaultClient()
    return HttpResponseRedirect(odesk_client.auth.auth_url())


def callback(request, redirect_url=None):
    odesk_client = DefaultClient()
    frob = request.GET.get('frob', None)
    if frob:
        try:
            token, auth_user = odesk_client.auth.get_token(frob)
        except Exception as exc:
            msg = "get_token(%(frob)r) failed with %(exc)s" % {
                'frob': frob,
                'exc': exc,
                'req': request,
            }
            logging.error(msg, exc_info=True)
            return HttpResponseRedirect(redirect_url or '/')
        encryption_key, encrypted_token = encrypt_token(token)

        request.session[ODESK_TOKEN_SESSION_KEY] = encrypted_token
        #TODO: Get rid of (conceptually correct) additional request
        #to odesk.com
        user = django_authenticate(token=token)
        if user:
            login(request, user)
        else:
            pass
            #Probably the odesk auth backend is missing.
            #Should we raise an error?
        redirect_url = request.session.pop(ODESK_REDIRECT_SESSION_KEY,
                                           redirect_url)
        response = HttpResponseRedirect(redirect_url or '/')
        expires = datetime.timedelta(hours=2) + datetime.datetime.utcnow()
        # string conversion for django 1.2 somehow doesn't work either,
        # so I use max_age
        response.set_cookie(ENCRYPTION_KEY_NAME, encryption_key,
                            expires=expires, max_age=60*60*2)
        return response

    else:
        return HttpResponseRedirect(odesk_client.auth.auth_url())
