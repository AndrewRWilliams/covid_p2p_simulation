import sys
import os
sys.path.append(os.getcwd())
import numpy as np
from config import *
from utils import _encode_message, _decode_message, binary_to_float
import operator
import datetime


""" This file contains the core of the side simulation, which is run on the output encounters from the main simulation.
It's primary functionality is to run the message clustering and risk prediction algorithms.
"""
class RiskModelBase:
    @classmethod
    def update_risk_encounter(self, human, now):
        raise "Unimplemented"

    @classmethod
    def update_risk_local(cls, human, now):
        """ This function calculates a risk score based on the person's symptoms."""
        # if they get tested, it takes TEST_DAYS to get the result, and they are quarantined for QUARANTINE_DAYS.
        # The test_timestamp is set to datetime.min, unless they get a positive test result.
        # Basically, once they know they have a positive test result, they have a risk of 1 until after quarantine days.
        if human.time_of_recovery < now:
            return 0.
        if human.time_of_death < now:
            return 0.
        if human.test_logs[1] and human.test_logs[0] < now + datetime.timedelta(days=2):
            return 1.

        reported_symptoms = human.reported_symptoms_at_time(now)
        if 'severe' in reported_symptoms:
            return 0.75
        if 'moderate' in reported_symptoms:
            return 0.5
        if 'mild' in reported_symptoms:
            return 0.25
        if len(reported_symptoms) > 3:
            return 0.25
        if len(reported_symptoms) > 1:
            return 0.1
        if len(reported_symptoms) > 0:
            return 0.05
        return 0.0

    @classmethod
    def add_message_to_cluster(cls, human, m_i):
        """ This function clusters new messages by scoring them against old messages in a sort of naive nearest neighbors approach"""
        # TODO: include risk level in clustering, currently only uses quantized uid
        # TODO: refactor to compare multiple clustering schemes
        # TODO: check for mutually exclusive messages in order to break up a group and re-run nearest neighbors
        m_i_enc = _encode_message(m_i)
        m_risk = binary_to_float("".join([str(x) for x in np.array(m_i[1].tolist()).astype(int)]), 0, 4)

        # otherwise score against previous messages
        scores = {}
        for m_enc, _ in human.M.items():
            m = _decode_message(m_enc)
            if m_i[0] == m[0] and m_i[2].day == m[2].day:
                scores[m_enc] = 3
            elif m_i[0][:3] == m[0][:3] and m_i[2].day - 1 == m[2].day:
                scores[m_enc] = 2
            elif m_i[0][:2] == m[0][:2] and m_i[2].day - 2 == m[2].day:
                scores[m_enc] = 1
            elif m_i[0][:1] == m[0][:1] and m_i[2].day - 2 == m[2].day:
                scores[m_enc] = 0

        if scores:
            max_score_message = max(scores.items(), key=operator.itemgetter(1))[0]
            human.M[m_i_enc] = {'assignment': human.M[max_score_message]['assignment'], 'previous_risk': m_risk, 'carry_over_transmission_proba': RISK_TRANSMISSION_PROBA}
        # if it's either the first message
        elif len(human.M) == 0:
            human.M[m_i_enc] = {'assignment': 0, 'previous_risk': m_risk, 'carry_over_transmission_proba': RISK_TRANSMISSION_PROBA}
        # if there was no nearby neighbor
        else:
            new_group = max([v['assignment'] for k, v in human.M.items()]) + 1
            human.M[m_i_enc] = {'assignment': new_group, 'previous_risk': m_risk, 'carry_over_transmission_proba': RISK_TRANSMISSION_PROBA}


class RiskModelLenka(RiskModelBase):
    @classmethod
    def update_risk_encounter(cls, human, message):
        # Get the binarized contact risk
        m_risk = binary_to_float("".join([str(x) for x in np.array(message.risk.tolist()).astype(int)]), 0, 4)
        human.update = m_risk * RISK_TRANSMISSION_PROBA


class RiskModelYoshua(RiskModelBase):
    @classmethod
    def update_risk_encounter(cls, human, message):
        """ This function updates an individual's risk based on the receipt of a new message"""

        # Get the binarized contact risk
        m_risk = binary_to_float("".join([str(x) for x in np.array(message.risk.tolist()).astype(int)]), 0, 4)

        update = 0
        if human.risk < m_risk:
            update = (m_risk - m_risk * human.risk) * RISK_TRANSMISSION_PROBA
        print(f"human.risk: {human.risk}, m_risk: {m_risk}, update: {update}")

        human.risk += update



class RiskModelEilif(RiskModelBase):
    @classmethod
    def update_risk_encounter(cls, human, message):
        """ This function updates an individual's risk based on the receipt of a new message"""
        cls.add_message_to_cluster(human, message)

        # Get the binarized contact risk
        m_risk = binary_to_float("".join([str(x) for x in np.array(message.risk.tolist()).astype(int)]), 0, 4)
        msg_enc = _encode_message(message)
        if msg_enc not in human.M:
            # update is delta_risk
            update = m_risk * RISK_TRANSMISSION_PROBA
        else:
            previous_risk = human.M[msg_enc]['previous_risk']
            carry_over_transmission_proba = human.M[msg_enc]['carry_over_transmission_proba']
            update = ((m_risk - previous_risk) * RISK_TRANSMISSION_PROBA + previous_risk * carry_over_transmission_proba)

        # Update contact history
        human.M[msg_enc]['previous_risk'] = m_risk
        human.M[msg_enc]['carry_over_transmission_proba'] = RISK_TRANSMISSION_PROBA * (1 - update)






