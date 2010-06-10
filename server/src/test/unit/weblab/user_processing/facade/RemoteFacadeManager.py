#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2009 University of Deusto
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
# This software consists of contributions made by many individuals, 
# listed below:
#
# Author: Pablo Orduña <pablo@ordunya.com>
# 
import sys
import unittest

try:
    import ZSI
except ImportError:
    ZSI_AVAILABLE = False
else:
    ZSI_AVAILABLE = True

import voodoo.sessions.SessionId as SessionId

import test.unit.configuration as configuration
import voodoo.configuration.ConfigurationManager as ConfigurationManager

import weblab.user_processing.facade.UserProcessingFacadeManager as UserProcessingFacadeManager
import weblab.facade.RemoteFacadeManagerCodes as RFCodes
import weblab.facade.RemoteFacadeManager as RFM
import weblab.user_processing.facade.UserProcessingFacadeCodes as UserProcessingRFCodes
import weblab.user_processing.Reservation as Reservation

import weblab.data.experiments.ExperimentAllowed as ExperimentAllowed
import weblab.data.experiments.Experiment as Experiment
import weblab.data.experiments.Category as Category
import weblab.data.Command as Command
import weblab.data.dto.Group as Group

from weblab.data.dto.User import User, Role

import weblab.exceptions.user_processing.UserProcessingExceptions as UserProcessingExceptions
import weblab.exceptions.WebLabExceptions as WebLabExceptions
import voodoo.gen.exceptions.exceptions as VoodooExceptions

class MockUPS(object):
    def __init__(self):
        super(MockUPS, self).__init__()
        self.arguments     = {}
        self.return_values = {}
        self.exceptions    = {}

    def logout(self, session_id):
        self.arguments['logout'] = (session_id,)
        if self.exceptions.has_key('logout'):
            raise self.exceptions['logout']
        return self.return_values['logout']
    
    def list_experiments(self, session_id):
        self.arguments['list_experiments'] = (session_id, )
        if self.exceptions.has_key('list_experiments'):
            raise self.exceptions['list_experiments']
        return self.return_values['list_experiments']

    def reserve_experiment(self, session_id, experiment, client_address):
        self.arguments['reserve_experiment'] = (session_id, experiment, client_address)
        if self.exceptions.has_key('reserve_experiment'):
            raise self.exceptions['reserve_experiment']
        return self.return_values['reserve_experiment']

    def finished_experiment(self, session_id):
        self.arguments['finished_experiment'] = (session_id, )
        if self.exceptions.has_key('finished_experiment'):
            raise self.exceptions['finished_experiment']
        return self.return_values['finished_experiment']

    def get_reservation_status(self, session_id):
        self.arguments['get_reservation_status'] = (session_id, )
        if self.exceptions.has_key('get_reservation_status'):
            raise self.exceptions['get_reservation_status']
        return self.return_values['get_reservation_status']

    def send_file(self, session_id, file_content, file_info):
        self.arguments['send_file'] = (session_id, file_content, file_info)
        if self.exceptions.has_key('send_file'):
            raise self.exceptions['send_file']
        return self.return_values['send_file']

    def send_command(self, session_id, command):
        self.arguments['send_command'] = (session_id, command)
        if self.exceptions.has_key('send_command'):
            raise self.exceptions['send_command']
        return self.return_values['send_command']

    def poll(self, session_id):
        self.arguments['poll'] = (session_id, )
        if self.exceptions.has_key('poll'):
            raise self.exceptions['poll']
        return self.return_values['poll']

    def get_user_information(self, session_id):
        self.arguments['get_user_information'] = (session_id, )
        if self.exceptions.has_key('get_user_information'):
            raise self.exceptions['get_user_information']
        return self.return_values['get_user_information']
    
    def get_groups(self, session_id):
        self.arguments['get_groups'] = (session_id, )
        if self.exceptions.has_key('get_groups'):
            raise self.exceptions['get_groups']
        return self.return_values['get_groups']
    
    def get_experiments(self, session_id):
        self.arguments['get_experiments'] = (session_id, )
        if self.exceptions.has_key('get_experiments'):
            raise self.exceptions['get_experiments']
        return self.return_values['get_experiments']

class UserProcessingFacadeManagerTestCase(unittest.TestCase):
    if ZSI_AVAILABLE:
        def setUp(self):

            self.cfg_manager   = ConfigurationManager.ConfigurationManager()
            self.cfg_manager.append_module(configuration)

            self.mock_ups      = MockUPS()

            server_admin_mail = self.cfg_manager.get_value(RFM.SERVER_ADMIN_EMAIL, RFM.DEFAULT_SERVER_ADMIN_EMAIL)
            self.weblab_general_error_message = RFM.UNEXPECTED_ERROR_MESSAGE_TEMPLATE % server_admin_mail 

            self.rfm = UserProcessingFacadeManager.UserProcessingRemoteFacadeManagerZSI(
                    self.cfg_manager,
                    self.mock_ups
                )

        def _generate_two_experiments(self):
            experimentA = Experiment.Experiment(
                    'weblab-pld',
                    Category.ExperimentCategory('WebLab-PLD experiments'),
                    'start_date',
                    'end_date'
                )
            experimentB = Experiment.Experiment(
                    'weblab-pld',
                    Category.ExperimentCategory('WebLab-PLD experiments'),
                    'start_date',
                    'end_date'
                )
            return experimentA, experimentB

        def _generate_experiments_allowed(self):
            experimentA, experimentB = self._generate_two_experiments()
            exp_allowedA = ExperimentAllowed.ExperimentAllowed(
                    experimentA,
                    100
                )
            exp_allowedB = ExperimentAllowed.ExperimentAllowed(
                    experimentB,
                    100
                )
            return exp_allowedA, exp_allowedB

        def _generate_groups(self):
            group1 = Group.Group("group 1")
            group11 = Group.Group("group 1.1")
            group12 = Group.Group("group 1.2")
            group2 = Group.Group("group 2")
            group1.add_child(group11)
            group1.add_child(group12)
            return group1, group2

        def test_return_logout(self):
            expected_sess_id = SessionId.SessionId("whatever")
        
            self.mock_ups.return_values['logout'] = expected_sess_id

            self.assertEquals(
                    expected_sess_id.id,
                    self.rfm.logout(expected_sess_id).id
                )
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['logout'][0].id
                )
        
        def test_return_list_experiments(self):
            expected_sess_id = SessionId.SessionId("whatever")
            experiments_allowed = self._generate_experiments_allowed()
        
            self.mock_ups.return_values['list_experiments'] = experiments_allowed

            self.assertEquals(
                    experiments_allowed,
                    self.rfm.list_experiments(expected_sess_id)
                )
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['list_experiments'][0].id
                )
        
        def test_return_reserve_experiment(self):
            expected_sess_id = SessionId.SessionId("whatever")
            experimentA, _ = self._generate_two_experiments()
            expected_reservation = Reservation.ConfirmedReservation(100)
        
            self.mock_ups.return_values['reserve_experiment'] = expected_reservation

            self.assertEquals(
                    expected_reservation,
                    self.rfm.reserve_experiment(
                        expected_sess_id, 
                        experimentA.to_experiment_id()
                    )
                )
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['reserve_experiment'][0].id
                )
            self.assertEquals(
                    experimentA.name,
                    self.mock_ups.arguments['reserve_experiment'][1].exp_name
                )
            self.assertEquals(
                    experimentA.category.name,
                    self.mock_ups.arguments['reserve_experiment'][1].cat_name
                )

        def test_return_finished_experiment(self):
            expected_sess_id = SessionId.SessionId("whatever")

            self.mock_ups.return_values['finished_experiment'] = None   

            self.rfm.finished_experiment(expected_sess_id)
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['finished_experiment'][0].id
                )
        
        def test_return_get_reservation_status(self):
            expected_sess_id = SessionId.SessionId("whatever")
        
            expected_reservation = Reservation.ConfirmedReservation(100)

            self.mock_ups.return_values['get_reservation_status'] = expected_reservation


            reservation = self.rfm.get_reservation_status(expected_sess_id)
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['get_reservation_status'][0].id
                )
            
            self.assertEquals(
                    expected_reservation.status,
                    reservation.status
                )

            self.assertEquals(
                    expected_reservation.time,
                    reservation.time
                )

        def test_return_send_file(self):
            expected_sess_id      = SessionId.SessionId("whatever")
            expected_file_content = "<content of the file>"

            self.mock_ups.return_values['send_file']        = None

            self.rfm.send_file(
                    expected_sess_id,
                    expected_file_content,
                    'program'
                )
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['send_file'][0].id
                )
            
            self.assertEquals(
                    expected_file_content,
                    self.mock_ups.arguments['send_file'][1]
                )

        def test_return_send_command(self):
            expected_sess_id = SessionId.SessionId("whatever")
            expected_command = Command.Command("ChangeSwitch on 9")

            self.mock_ups.return_values['send_command'] = None

            self.rfm.send_command(
                    expected_sess_id,
                    expected_command
                )
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['send_command'][0].id
                )
            
            self.assertEquals(
                    expected_command.get_command_string(),
                    self.mock_ups.arguments['send_command'][1].get_command_string()
                )

        def test_return_poll(self):
            expected_sess_id = SessionId.SessionId("whatever")
        
            self.mock_ups.return_values['poll'] = None

            self.rfm.poll(expected_sess_id)
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['poll'][0].id
                )

        def test_return_get_user_information(self):
            expected_sess_id = SessionId.SessionId("whatever")

            expected_user_information = User(
                    'porduna', 
                    'Pablo Orduna', 
                    'weblab@deusto.es',
                    Role("student")
                )
        
            self.mock_ups.return_values['get_user_information'] = expected_user_information

            user_information = self.rfm.get_user_information(expected_sess_id)
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['get_user_information'][0].id
                )

            self.assertEquals(
                    expected_user_information.login,
                    user_information.login
                )

            self.assertEquals(
                    expected_user_information.full_name,
                    user_information.full_name
                )

            self.assertEquals(
                    expected_user_information.email,
                    user_information.email
                )

            self.assertEquals(
                    expected_user_information.role.name,
                    user_information.role.name
                )
        
        def test_return_get_groups(self):
            expected_sess_id = SessionId.SessionId("whatever")
            groups = self._generate_groups()
        
            self.mock_ups.return_values['get_groups'] = groups

            self.assertEquals(
                    groups,
                    self.rfm.get_groups(expected_sess_id)
                )
            
            self.assertEquals(
                    expected_sess_id.id,
                    self.mock_ups.arguments['get_groups'][0].id
                )

        def _generate_real_mock_raising(self, method, exception, message):
            self.mock_ups.exceptions[method] = exception(message)
     

        def _test_exception(self, method, args, exc_to_raise, exc_message, expected_code, expected_exc_message):
            self._generate_real_mock_raising(method, exc_to_raise, exc_message )

            try:
                getattr(self.rfm, method)(*args)
                self.fail('exception expected')
            except ZSI.Fault, e:
                self.assertEquals(expected_code, e.code)
                self.assertEquals(expected_exc_message, e.string)
        
        def _test_general_exceptions(self, method, *args):
            MESSAGE = "The exception message"
    
            # Production mode: A general error message is received
            self.cfg_manager._set_value(RFM.DEBUG_MODE, False)

            self._test_exception(method, args,  
                            UserProcessingExceptions.UserProcessingException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.WEBLAB_GENERAL_EXCEPTION_CODE, self.weblab_general_error_message)

            self._test_exception(method, args,  
                            WebLabExceptions.WebLabException, MESSAGE, 
                            'ZSI:' + RFCodes.WEBLAB_GENERAL_EXCEPTION_CODE, self.weblab_general_error_message)

            self._test_exception(method, args,  
                            VoodooExceptions.GeneratorException, MESSAGE, 
                            'ZSI:' + RFCodes.WEBLAB_GENERAL_EXCEPTION_CODE, self.weblab_general_error_message)

            self._test_exception(method, args,  
                            Exception, MESSAGE, 
                            'ZSI:' + RFCodes.WEBLAB_GENERAL_EXCEPTION_CODE, self.weblab_general_error_message)            
               
            # Debug mode: The error message is received
            self.cfg_manager._set_value(RFM.DEBUG_MODE, True)

            self._test_exception(method, args,  
                            UserProcessingExceptions.UserProcessingException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.UPS_GENERAL_EXCEPTION_CODE, MESSAGE)

            self._test_exception(method, args,  
                            WebLabExceptions.WebLabException, MESSAGE, 
                            'ZSI:' + RFCodes.WEBLAB_GENERAL_EXCEPTION_CODE, MESSAGE)

            self._test_exception(method, args,  
                            VoodooExceptions.GeneratorException, MESSAGE, 
                            'ZSI:' + RFCodes.VOODOO_GENERAL_EXCEPTION_CODE, MESSAGE)

            self._test_exception(method, args,  
                            Exception, MESSAGE, 
                            'ZSI:' + RFCodes.PYTHON_GENERAL_EXCEPTION_CODE, MESSAGE)            
               
        def test_exception_logout(self):            
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('logout', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
            
            self._test_general_exceptions('logout', expected_sess_id)


        def test_exception_list_experiments(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('list_experiments', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
            
            self._test_general_exceptions('list_experiments', expected_sess_id)
                

        def test_exception_reserve_experiment(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            experimentA, _ = self._generate_two_experiments()
            
            self._test_exception('reserve_experiment', (expected_sess_id, experimentA.to_experiment_id()),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)            

            self._test_exception('reserve_experiment', (expected_sess_id, experimentA.to_experiment_id()),  
                            UserProcessingExceptions.UnknownExperimentIdException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_UNKNOWN_EXPERIMENT_ID_EXCEPTION_CODE, MESSAGE)            
            
            self._test_general_exceptions('reserve_experiment', expected_sess_id, experimentA.to_experiment_id())
                
        def test_exception_finished_experiment(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('finished_experiment', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
                
            self._test_exception('finished_experiment', (expected_sess_id,),   
                            UserProcessingExceptions.NoCurrentReservationException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_NO_CURRENT_RESERVATION_EXCEPTION_CODE, MESSAGE)                   
                
            self._test_general_exceptions('finished_experiment', expected_sess_id)
                

        def test_exception_get_reservation_status(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('get_reservation_status', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
                
            self._test_exception('get_reservation_status', (expected_sess_id,),   
                            UserProcessingExceptions.NoCurrentReservationException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_NO_CURRENT_RESERVATION_EXCEPTION_CODE, MESSAGE)                   
                
            self._test_general_exceptions('get_reservation_status', expected_sess_id)
                
        def test_exception_send_file(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            FILE_CONTENT = 'whatever'
            
            self._test_exception('send_file', (expected_sess_id, FILE_CONTENT, 'program',),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
                
            self._test_exception('send_file', (expected_sess_id, FILE_CONTENT, 'program',),  
                            UserProcessingExceptions.NoCurrentReservationException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_NO_CURRENT_RESERVATION_EXCEPTION_CODE, MESSAGE)                   

            self._test_general_exceptions('send_file', expected_sess_id, FILE_CONTENT, 'program')

        def test_exception_send_command(self):            
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            COMMAND = Command.Command('whatever')
            
            self._test_exception('send_command', (expected_sess_id, COMMAND,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
            
            self._test_exception('send_command', (expected_sess_id, COMMAND,),   
                            UserProcessingExceptions.NoCurrentReservationException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_NO_CURRENT_RESERVATION_EXCEPTION_CODE, MESSAGE)                   

            self._test_general_exceptions('send_command', expected_sess_id, COMMAND)
                
        def test_exception_poll(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('poll', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
                
            self._test_exception('poll', (expected_sess_id,),   
                            UserProcessingExceptions.NoCurrentReservationException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_NO_CURRENT_RESERVATION_EXCEPTION_CODE, MESSAGE)                   
                
            self._test_general_exceptions('poll', expected_sess_id)
                

        def test_exception_get_user_information(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('get_user_information', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
                
            self._test_general_exceptions('get_user_information', expected_sess_id)


        def test_exception_get_groups(self):
            MESSAGE = "The exception message"
            expected_sess_id  = SessionId.SessionId("whatever")
            
            self._test_exception('get_groups', (expected_sess_id,),  
                            UserProcessingExceptions.SessionNotFoundException, MESSAGE, 
                            'ZSI:' + UserProcessingRFCodes.CLIENT_SESSION_NOT_FOUND_EXCEPTION_CODE, MESSAGE)
            
            self._test_general_exceptions('get_groups', expected_sess_id)
            
    else:
        print >> sys.stderr, "Optional module 'ZSI' not available. Tests in UserProcessingFacadeManagerTestCase skipped."

def suite():
    return unittest.makeSuite(UserProcessingFacadeManagerTestCase)

if __name__ == '__main__':
    unittest.main()

