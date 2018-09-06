# this module handles SMS logic...
# the module should be local to the UTL SMPP server though i dint take time to
# implement server security as UTL already did that for us
#
# NB: i had implemented this logic in C++ but due to the possibility of changing the
# server/user information from time to time, i re-implemented it in Python and added
# a monitoring script that should restart the SMS engine in case any information changes
#
#
# Note: Vincent from UTL had mensioned a unix tool `kannel` but i dint have the time to study
# the tool to use it(fully grasping the internal workings of a program can take time) and i dint
# want to take chances deploying a tool whose code i hadnt personally read line by line!
#
#
# Author:      Bukman <glayn2bukman@gmail.com>
# UTL contact: Kevin <kevin.okura@utl.co.ug>

METADATA = {
    "uname":        "jerm",
    "pswd":         "jerm321",
    "service":      "SMPP",
    "bind-mode":    "transmitter",
    "host":         "192.100.202.139",
    "port":         6200,
    
    "source-number": "256714442200",
    # set the prefix as this service is ONLY intended for the UTL-AMS RT
    "number-prefix": "25671",
}

SETUP_OK = False 
CLIENT = None

import logging
import sys

import smpplib2.gsm
import smpplib2.client
import smpplib2.consts

def received_message_handler(pdu):
    return sys.stdout.write('SMSC sent a request {} {}\n'.format(pdu.sequence, pdu.message_id))

def smsc_message_resp_handler(pdu):
    return sys.stdout.write('SMSC sent a response to our request {} {}\n'.format(pdu.sequence, pdu.message_id))

def esme_sent_msg_handler(ssm):
    return sys.stdout.write('sending message: {} with sequence_number:{} to phone_number: {}'.format(ssm.short_message, ssm.destination_addr, ssm.sequence))

def clean_number(number):
    """
    convert number to what the UTL SMTP servre expects (25671*)
    """
    number = str(number)
    
    if len(number)<10: return False,number
    
    if number[0]=="+": number = number[1:]
    if number[0]=="0": number = "256"+number[1:]
    
    if not number.startswith(METADATA["number-prefix"]): return False,number
    
    if len(number)!=12: return False,number
    
    for c in number:
        if ord(c)>ord('9') or ord(c)<ord('0'): return False,number
    
    return True,number

def setup(*args):
    """
    handle any setups required here...
    this may be username-password or gateway setup code
    
    NB: that args is unix-style thus for verbose, you can provide `--verbose` or `-v`
        this makes it easy to communicate with setup from the commandline!
    
    """
    
    verbose = ("--verbose" in args) or ("-v" in args)
    
    if verbose:
        print "\033[0;33m[UTL-AMS SMS] INFO: \033[0m setting up SMPP service..."

    global CLIENT, SETUP_OK

    CLIENT = None
    SETUP_OK = False

    # verbose mode for unit-tests
    #if verbose:
    #    logging.basicConfig(level='DEBUG')

    client = smpplib2.client.Client(METADATA["host"], METADATA["port"])

    client.set_message_response_handler(smsc_message_resp_handler)
    client.set_message_received_handler(received_message_handler)
    client.set_esme_sent_msg_handler(esme_sent_msg_handler)

    try:
        client.connect()
    except smpplib2.exceptions.ConnectionError as e:
        print "\033[1;31m[UTL-AMS SMS] ERROR:\033[0m",e
        return False
    
    if METADATA["bind-mode"]=="transmitter":
        client.bind_transmitter(system_id=METADATA["uname"], password=METADATA["pswd"])
    elif METADATA["bind-mode"]=="transceiver":
        client.bind_transceiver(system_id=METADATA["uname"], password=METADATA["pswd"])

    CLIENT = client
    SETUP_OK = True

    if METADATA["bind-mode"]=="transceiver":
        client.listen()
        
def send(dest, msg, *setup_args):
    """
    if SETUP_OK, then send message. otherwise, attempt setup
    return bool
    
    NB: due to the blocking nature of this function, it should be called in a separate thread
    """
    dest = clean_number(dest)
    
    if not dest[0]: 
        print "invalid phone number given"
        return False

    dest = dest[1]

    if not SETUP_OK:
        setup(*setup_args)
        if not SETUP_OK:
            return False

    parts, encoding_flag, msg_type_flag = smpplib2.gsm.make_parts(unicode(msg))
    

    for part in parts:
        pdu = CLIENT.send_message(
            source_addr_ton=smpplib2.consts.SMPP_TON_INTL,
            #source_addr_npi=smpplib2.consts.SMPP_NPI_ISDN,
            # Make sure it is a byte string, not unicode:
            source_addr=METADATA["source-number"],

            dest_addr_ton=smpplib2.consts.SMPP_TON_INTL,
            #dest_addr_npi=smpplib2.consts.SMPP_NPI_ISDN,
            # Make sure thease two params are byte strings, not unicode:
            destination_addr=dest,
            short_message=part,

            data_coding=encoding_flag,
            esm_class=msg_type_flag,
            registered_delivery=True,
        )
        print(pdu.sequence)

    return True

if __name__=="__main__":
    import sys
    test_numbers = ["0713520215", "256714225204"]
    print "sms sent successfully!" if send("0713520215", "UTL-AMS sms testing 1.2.3", *(sys.argv[1:] if len(sys.argv)>1 else ())) else "failed to send sms"
