#!/usr/bin/env python
#-*-*- encoding: utf-8 -*-*-
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
import time
import datetime

import json

from voodoo.log import logged
import voodoo.LogLevel as LogLevel
import voodoo.log as log
import voodoo.AdminNotifier as AdminNotifier

import weblab.exceptions.user_processing.CoordinatorExceptions as CoordExc

import weblab.user_processing.coordinator.CoordinationDatabaseManager as CoordinationDatabaseManager
import weblab.user_processing.coordinator.ResourcesManager as ResourcesManager
import weblab.user_processing.coordinator.ReservationsManager as ReservationsManager
import weblab.user_processing.coordinator.PostReservationDataManager as PostReservationDataManager
import weblab.user_processing.coordinator.Confirmer as Confirmer
import weblab.user_processing.coordinator.Scheduler as Scheduler
import weblab.user_processing.coordinator.MetaScheduler as MetaScheduler
import weblab.user_processing.coordinator.TemporalInformationStore as TemporalInformationStore

import weblab.user_processing.coordinator.PriorityQueueScheduler as PriorityQueueScheduler
import weblab.user_processing.coordinator.ResourcesCheckerThread as ResourcesCheckerThread

PRIORITY_QUEUE = 'PRIORITY_QUEUE'

SCHEDULING_SYSTEMS = {
        PRIORITY_QUEUE : PriorityQueueScheduler.PriorityQueueScheduler
    }

CORE_SCHEDULING_SYSTEMS = 'core_scheduling_systems'

RESOURCES_CHECKER_FREQUENCY = 'core_resources_checker_frequency'
DEFAULT_RESOURCES_CHECKER_FREQUENCY = 30 # seconds

POST_RESERVATION_EXPIRATION_TIME = 'core_post_reservation_expiration_time'
DEFAULT_POST_RESERVATION_EXPIRATION_TIME = 24 * 3600 # 1 day

RESOURCES_CHECKER_GENERAL_RECIPIENTS = 'core_resources_checker_general_recipients'
DEFAULT_RESOURCES_GENERAL_CHECKER_RECIPIENTS = ()

RESOURCES_CHECKER_PARTICULAR_RECIPIENTS = 'core_resources_checker_particular_recipients'
DEFAULT_RESOURCES_PARTICULAR_CHECKER_RECIPIENTS = {
            # "inst1:ud-pld@PLD Experiments" : ['admin1@whatever.edu', 'admin2@whatever.edu']
        }

RESOURCES_CHECKER_NOTIFICATIONS_ENABLED = 'core_resources_checker_notifications_enabled'
DEFAULT_RESOURCES_CHECKER_NOTIFICATIONS_ENABLED = False

FINISH_FINISHED_MESSAGE = 'finished'
FINISH_DATA_MESSAGE      = 'data'
FINISH_ASK_AGAIN_MESSAGE = 'ask_again'

class TimeProvider(object):
    def get_time(self):
        return time.time()

    def get_datetime(self):
        return datetime.datetime.utcnow()

class Coordinator(object):

    CoordinatorTimeProvider = TimeProvider

    def __init__(self, locator, cfg_manager, ConfirmerClass = Confirmer.ReservationConfirmer):
        self.cfg_manager = cfg_manager

        self.notifier = AdminNotifier.AdminNotifier(self.cfg_manager)
        self.notifications_enabled = self.cfg_manager.get_value(RESOURCES_CHECKER_NOTIFICATIONS_ENABLED, DEFAULT_RESOURCES_CHECKER_NOTIFICATIONS_ENABLED)

        coordination_database_manager = CoordinationDatabaseManager.CoordinationDatabaseManager(cfg_manager)
        self._session_maker = coordination_database_manager.session_maker

        self.locator   = locator # Used by ResourcesChecker
        self.confirmer = ConfirmerClass(self, locator)

        self.time_provider = self.CoordinatorTimeProvider()

        self.reservations_manager          = ReservationsManager.ReservationsManager(self._session_maker)
        self.resources_manager             = ResourcesManager.ResourcesManager(self._session_maker)
        self.post_reservation_data_manager = PostReservationDataManager.PostReservationDataManager(self._session_maker, self.time_provider)
        self.meta_scheduler                = MetaScheduler.MetaScheduler()

        self.initial_store  = TemporalInformationStore.TemporalInformationStore()
        self.finished_store = TemporalInformationStore.TemporalInformationStore()


        import weblab.user_processing.UserProcessingServer as UserProcessingServer
        clean = cfg_manager.get_value(UserProcessingServer.WEBLAB_USER_PROCESSING_SERVER_CLEAN_COORDINATOR, True)

        if clean:
            resources_checker_frequency = cfg_manager.get_value(RESOURCES_CHECKER_FREQUENCY, DEFAULT_RESOURCES_CHECKER_FREQUENCY)
            ResourcesCheckerThread.set_coordinator(self, resources_checker_frequency)


        post_reservation_expiration_time = cfg_manager.get_value(POST_RESERVATION_EXPIRATION_TIME, DEFAULT_POST_RESERVATION_EXPIRATION_TIME)
        self.expiration_delta = datetime.timedelta(seconds=post_reservation_expiration_time)

        # 
        # The system administrator must define what scheduling system is used by each resource type
        # For instance:
        # 
        # scheduling_systems = {
        #                  "pld boards"     : ("PRIORITY_QUEUE", {}),
        #                  "fpga boards"    : ("PRIORITY_QUEUE", {}),
        #                  "vm experiments" : ("BOOKING", { 'slots' : 30 * 1000 }), # Slots of 30 minutes
        #                  "something else" : ("EXTERNAL", { 'address' : 'http://192.168.1.50:8080/SchedulingServer', 'protocol' : 'SOAP' }) # If somebody else has implemented the scheduling schema in other language
        #            }
        # 
        self.schedulers = {}
        scheduling_systems = cfg_manager.get_value(CORE_SCHEDULING_SYSTEMS)
        for resource_type_name in scheduling_systems:
            scheduling_system, arguments = scheduling_systems[resource_type_name]
            if not scheduling_system in SCHEDULING_SYSTEMS:
                raise CoordExc.UnregisteredSchedulingSystemException("Unregistered scheduling system: %s" % scheduling_system)
            SchedulingSystemClass = SCHEDULING_SYSTEMS[scheduling_system]
            
            generic_scheduler_arguments = Scheduler.GenericSchedulerArguments(self.cfg_manager, resource_type_name, self.reservations_manager, self.resources_manager, self.confirmer, self._session_maker, self.time_provider)

            self.schedulers[resource_type_name] = SchedulingSystemClass(generic_scheduler_arguments, **arguments)

    ##########################################################################
    # 
    #   Methods to retrieve the proper schedulers
    # 
    def _get_schedulers_per_reservation(self, reservation_id):
        experiment_id = self.reservations_manager.get_experiment_id(reservation_id)
        resource_type_names = self.resources_manager.get_resource_types_by_experiment_id(experiment_id)
        return [    self.schedulers[resource_type_name]
                    for resource_type_name in resource_type_names ]

    def _get_schedulers_per_experiment_instance_id(self, experiment_instance_id):
        return self._get_schedulers_per_experiment_id(experiment_instance_id.to_experiment_id())

    def _get_scheduler_per_resource(self, resource):
        return self.schedulers[resource.resource_type]

    def _get_schedulers_per_experiment_id(self, experiment_id):
        schedulers = []
        for resource_type_name in self.resources_manager.get_resource_types_by_experiment_id(experiment_id):
            if resource_type_name not in self.schedulers:
                raise CoordExc.ExperimentNotFoundException("Unregistered resource type name: %s. Check the %s property." % (resource_type_name, CORE_SCHEDULING_SYSTEMS))
            schedulers.append(self.schedulers[resource_type_name])
        return schedulers

    ###########################################################################
    # 
    # General experiments and sessions management
    # 
    @logged()
    def add_experiment_instance_id(self, laboratory_coord_address, experiment_instance_id, resource):
        session = self._session_maker()
        try:
            self.resources_manager.add_experiment_instance_id(session, laboratory_coord_address, experiment_instance_id, resource)
            session.commit()
        finally:
            session.close()

    @logged()
    def list_experiments(self):
        return self.resources_manager.list_experiments()

    @logged()
    def list_laboratories_addresses(self):
        return self.resources_manager.list_laboratories_addresses()

    @logged()
    def list_resource_types(self):
        return self.schedulers.keys()

    @logged()
    def list_sessions(self, experiment_id):
        """ list_sessions( experiment_id ) -> { session_id : status } """

        reservation_ids = self.reservations_manager.list_sessions(experiment_id)
        
        result = {}
        for reservation_id in reservation_ids:
            try:
                schedulers = self._get_schedulers_per_reservation(reservation_id)
                best_reservation_status = self.meta_scheduler.query_best_reservation_status(schedulers, reservation_id)
            except CoordExc.CoordinatorException:
                # The reservation_id may expire since we called list_sessions,
                # so if there is a coordinator exception we just skip this 
                # reservation_id
                continue
            result[reservation_id] = best_reservation_status
        return result

    @logged()
    def mark_experiment_as_broken(self, experiment_instance_id, messages = []):
        resource_instance = self.resources_manager.get_resource_instance_by_experiment_instance_id(experiment_instance_id)
        return self.mark_resource_as_broken(resource_instance, messages)

    @logged()
    def mark_resource_as_broken(self, resource_instance, messages = []):
        scheduler = self._get_scheduler_per_resource(resource_instance)

        anything_changed = False
        session = self._session_maker()
        try:
            changed = scheduler.removing_current_resource_slot(session, resource_instance)
            anything_changed = anything_changed or changed

            changed = self.resources_manager.mark_resource_as_broken(session, resource_instance)
            anything_changed = anything_changed or changed
            if anything_changed:
                session.commit()
        finally:
            session.close()

        if anything_changed:
            log.log( Coordinator, LogLevel.Warning,
                    "Resource %s marked as broken: %r" % (resource_instance, messages) )

            if self.notifications_enabled:
                self._notify_experiment_status('broken', resource_instance, messages)

    @logged()
    def mark_resource_as_fixed(self, resource_instance):
        session = self._session_maker()
        try:
            anything_changed = self.resources_manager.mark_resource_as_fixed(session, resource_instance)
            if anything_changed:
                session.commit()
        finally:
            session.close()

        if anything_changed:
            log.log( Coordinator, LogLevel.Warning,
                    "Resource %s marked as fixed" % resource_instance )

            if self.notifications_enabled:
                self._notify_experiment_status('fixed', resource_instance)

    def _notify_experiment_status(self, new_status, resource_instance, messages = []):
        experiment_instance_ids = self.resources_manager.list_experiment_instance_ids_by_resource(resource_instance)
        if new_status == 'fixed':
            what = 'work again'
        else:
            what = 'not work'
        body = """The resource %s has changed its status to: %s\n\nTherefore the following experiment instances will %s:\n\n""" % (
                resource_instance, new_status, what)

        for experiment_instance_id in experiment_instance_ids:
            body += ("\t%s\n" % experiment_instance_id.to_weblab_str())

        if len(messages) > 0:
            body += "\nReasons: %r\n\nThe WebLab-Deusto system" % messages
        recipients = self._retrieve_recipients(experiment_instance_ids)
        subject = "[WebLab] Experiment %s: %s" % (resource_instance, new_status)

        if len(recipients) > 0:
            self.notifier.notify( recipients = recipients, body = body, subject = subject)

    def _retrieve_recipients(self, experiment_instance_ids):
        recipients = ()
        server_admin = self.cfg_manager.get_value(AdminNotifier.SERVER_ADMIN_NAME, None)
        if server_admin is not None:
            if server_admin.find(","):
                server_admins = tuple(server_admin.replace(" ","").split(","))
            else:
                server_admins = (server_admin,)
            recipients += server_admins

        general_recipients = self.cfg_manager.get_value(RESOURCES_CHECKER_GENERAL_RECIPIENTS, DEFAULT_RESOURCES_GENERAL_CHECKER_RECIPIENTS)
        recipients += tuple(general_recipients)

        for experiment_instance_id in experiment_instance_ids:
            particular_recipients = self.cfg_manager.get_value(RESOURCES_CHECKER_PARTICULAR_RECIPIENTS, DEFAULT_RESOURCES_PARTICULAR_CHECKER_RECIPIENTS)
            experiment_particular_recipients = particular_recipients.get(experiment_instance_id.to_weblab_str(), ())
            recipients += tuple(experiment_particular_recipients)

        return tuple(set(recipients))

    ##########################################################################
    # 
    # Perform a new reservation
    # 
    @logged()
    def reserve_experiment(self, experiment_id, time, priority, client_initial_data):
        """
        priority: the less, the more priority
        """
        reservation_id = self.reservations_manager.create(experiment_id, client_initial_data, self.time_provider.get_datetime)
        schedulers = self._get_schedulers_per_experiment_id(experiment_id)
        all_reservation_status = []
        for scheduler in schedulers:
            reservation_status = scheduler.reserve_experiment(reservation_id, experiment_id, time, priority)
            all_reservation_status.append(reservation_status)
        return self.meta_scheduler.select_best_reservation_status(all_reservation_status)

    #######################################################################
    # 
    # Given a reservation_id, it returns in which state the reservation is
    # 
    @logged()
    def get_reservation_status(self, reservation_id):
        try:
            schedulers = self._get_schedulers_per_reservation(reservation_id)
            return self.meta_scheduler.query_best_reservation_status(schedulers, reservation_id)
        except CoordExc.ExpiredSessionException:
            reservation_status = self.post_reservation_data_manager.find(reservation_id)
            if reservation_status is not None:
                return reservation_status
            raise

    ################################################################
    #
    # Called when it is confirmed by the Laboratory Server.
    #
    @logged()
    def confirm_experiment(self, experiment_instance_id, reservation_id, lab_session_id, server_initialization_response, initial_time, end_time):

        default_still_initialing      = False
        default_batch                 = False
        default_initial_configuration = "{}"
        if server_initialization_response is None or server_initialization_response == 'ok' or server_initialization_response == '':
            still_initializing = default_still_initialing
            batch = default_batch
            initial_configuration = default_initial_configuration
        else:
            try:
                response = json.loads(server_initialization_response)
                still_initializing    = response.get('keep_initializing', default_still_initialing)
                batch                 = response.get('batch', default_batch)
                initial_configuration = response.get('initial_configuration', default_initial_configuration)
            except Exception, e:
                log.log( Coordinator, log.LogLevel.Error, "Could not parse experiment server response: %s; %s; using default values" % (e, server_initialization_response) )
                log.log_exc( Coordinator, log.LogLevel.Warning )
                still_initializing    = default_still_initialing
                batch                 = default_batch
                initial_configuration = default_initial_configuration

        self.initial_store.put(reservation_id, initial_configuration, initial_time, end_time)
        now = self.time_provider.get_datetime()
        self.post_reservation_data_manager.create(reservation_id, now, now + self.expiration_delta, json.dumps(initial_configuration))

        if still_initializing:
            # TODO XXX 
            # TODO XXX: maybe it does not make sense. Given that finish also can return a result
            raise NotImplementedError("Not yet implemented: still_initializing")

        if batch: # It has already finished, so make this experiment available to others
            self.finish_reservation(reservation_id)
            return

        schedulers = self._get_schedulers_per_reservation(reservation_id)
        for scheduler in schedulers:
            scheduler.confirm_experiment(reservation_id, lab_session_id, initial_configuration)

    ################################################################
    #
    # Called when the Laboratory Server states that the experiment
    # was cleaned
    #
    @logged()
    def confirm_resource_disposal(self, lab_coordaddress, reservation_id, lab_session_id, experiment_instance_id, experiment_response, initial_time, end_time):

        experiment_finished  = True
        information_to_store = None
        time_remaining       = 0.5 # Every half a second by default

        if experiment_response is None or experiment_response == 'ok' or experiment_response == '':
            pass # Default value
        else:
            try:
                response = json.loads(experiment_response)
                experiment_finished   = response.get(FINISH_FINISHED_MESSAGE, experiment_finished)
                time_remaining        = response.get(FINISH_ASK_AGAIN_MESSAGE, time_remaining)
                information_to_store  = response.get(FINISH_DATA_MESSAGE, information_to_store)
            except Exception, e:
                log.log( Coordinator, log.LogLevel.Error, "Could not parse experiment server finishing response: %s; %s" % (e, experiment_response) )
                log.log_exc( Coordinator, log.LogLevel.Warning )
                
        if not experiment_finished:
            time.sleep(time_remaining)
            # We just ignore the data retrieved, if any, and perform the query again
            self.confirmer.enqueue_free_experiment(lab_coordaddress, reservation_id, lab_session_id, experiment_instance_id)
            return
        else:
            # Otherwise we mark it as finished
            self.post_reservation_data_manager.finish(reservation_id, json.dumps(information_to_store))
            # and we remove the resource
            session = self._session_maker()
            try:
                resource_instance = self.resources_manager.get_resource_instance_by_experiment_instance_id(experiment_instance_id)
                self.resources_manager.release_resource_instance(session, resource_instance)
                session.commit()
            finally:
                session.close()
                self.finished_store.put(reservation_id, information_to_store, initial_time, end_time)

            # It's done here so it's called often enough
            self.post_reservation_data_manager.clean_expired()


    ################################################################
    #
    # Called when the user disconnects or finishes the experiment.
    #
    @logged()
    def finish_reservation(self, reservation_id):
        schedulers = self._get_schedulers_per_reservation(reservation_id)
        for scheduler in schedulers:
            scheduler.finish_reservation(reservation_id)
        # The reservations_manager must remove the session once (not once per scheduler)
        session = self._session_maker()
        try:
            self.reservations_manager.delete(session, reservation_id)
            session.commit()
        finally:
            session.close()

    def _clean(self):
        for scheduler in self.schedulers.values():
            scheduler._clean()

        self.reservations_manager._clean()
        self.resources_manager._clean()
        self.post_reservation_data_manager._clean()

