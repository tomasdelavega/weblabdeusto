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
# Author: Jaime Irurzun <jaime.irurzun@gmail.com>
# 

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import desc

from voodoo.log import logged

import weblab.database.Model as Model

import weblab.database.DatabaseMySQLGateway as dbMySQLGateway

import weblab.data.dto.ExperimentAllowed as ExperimentAllowed

import weblab.exceptions.database.DatabaseExceptions as DbExceptions

WEBLAB_DB_USERNAME_PROPERTY = 'weblab_db_username'
DEFAULT_WEBLAB_DB_USERNAME  = 'weblab'

WEBLAB_DB_PASSWORD_PROPERTY = 'weblab_db_password'

def getconn():
    import MySQLdb as dbi
    return dbi.connect(user = DatabaseGateway.user, passwd = DatabaseGateway.password,
            host = DatabaseGateway.host, db = DatabaseGateway.dbname, client_flag = 2)

def admin_panel_operation(func):
    """It checks if the requesting user has the admin_panel_access permission with full_privileges (temporal policy)."""
    def proxy(self, user_login, *args, **kargs):
        session = self.Session()
        try:
            user = self._get_user(session, user_login)
            admin_panel_access_permissions = self._gather_permissions(session, user, "admin_panel_access")
            if len(admin_panel_access_permissions) > 0:
                # The only requirement for now is to have full_privileges, this will be changed in further versions
                if self._get_bool_parameter_from_permission(session, admin_panel_access_permissions[0], "full_privileges"):
                    return func(self, user_login, *args, **kargs)
            return ()
        finally:
            session.close()
    return proxy

DEFAULT_VALUE = object()

class DatabaseGateway(dbMySQLGateway.AbstractDatabaseGateway):

    user     = None
    password = None
    host     = None
    dbname   = None

    pool = sqlalchemy.pool.QueuePool(getconn, pool_size=15, max_overflow=20)

    def __init__(self, cfg_manager):
        super(DatabaseGateway, self).__init__(cfg_manager)
       
        DatabaseGateway.user     = cfg_manager.get_value(WEBLAB_DB_USERNAME_PROPERTY, DEFAULT_WEBLAB_DB_USERNAME)
        DatabaseGateway.password = cfg_manager.get_value(WEBLAB_DB_PASSWORD_PROPERTY)
        DatabaseGateway.host     = self.host
        DatabaseGateway.dbname   = self.database_name

        connection_url = "mysql://%(USER)s:%(PASSWORD)s@%(HOST)s/%(DATABASE)s" % \
                            { "USER":     self.user,
                              "PASSWORD": self.password,
                              "HOST":     self.host,
                              "DATABASE": self.dbname  }
        self.Session = sessionmaker(bind=create_engine(connection_url, echo=False, convert_unicode=True, pool = self.pool))

    @logged()
    def get_user_by_name(self, user_login):
        session = self.Session()
        try:
            return self._get_user(session, user_login).to_dto()
        finally:
            session.close()


    @logged()
    def list_experiments(self, user_login):
        session = self.Session()
        try:
            user = self._get_user(session, user_login)
            permissions = self._gather_permissions(session, user, 'experiment_allowed')
            
            grouped_experiments = {}
            for permission in permissions:
                p_permanent_id = self._get_parameter_from_permission(session, permission, 'experiment_permanent_id')
                p_category_id = self._get_parameter_from_permission(session, permission, 'experiment_category_id')
                p_time_allowed = self._get_float_parameter_from_permission(session, permission, 'time_allowed')
                p_priority = self._get_int_parameter_from_permission(session, permission, 'priority', ExperimentAllowed.DEFAULT_PRIORITY)
                
                experiment = session.query(Model.DbExperiment).filter_by(name=p_permanent_id).filter(Model.DbExperimentCategory.name==p_category_id).one() 
                experiment_allowed = ExperimentAllowed.ExperimentAllowed(experiment.to_business(), p_time_allowed, p_priority)
                
                experiment_unique_id = p_permanent_id+"@"+p_category_id
                if grouped_experiments.has_key(experiment_unique_id):
                    grouped_experiments[experiment_unique_id].append(experiment_allowed)
                else:
                    grouped_experiments[experiment_unique_id] = [experiment_allowed]
                
            # If any experiment is duplicated, only the less restrictive one is given
            experiments = []
            for experiment_unique_id in grouped_experiments:
                less_restrictive_experiment_allowed = grouped_experiments[experiment_unique_id][0]
                for experiment_allowed in grouped_experiments[experiment_unique_id]:
                    if experiment_allowed.time_allowed > less_restrictive_experiment_allowed.time_allowed:
                        less_restrictive_experiment_allowed = experiment_allowed
                experiments.append(less_restrictive_experiment_allowed)

            experiments.sort(lambda x,y: cmp(x.experiment.category.name, y.experiment.category.name))
            return tuple(experiments)
        finally:
            session.close()

    @logged()
    def store_experiment_usage(self, user_login, reservation_info, experiment_usage):
        session = self.Session()
        try:
            use = Model.DbUserUsedExperiment(
                        self._get_user(session, user_login),
                        self._get_experiment(session, experiment_usage.experiment_id.exp_name, experiment_usage.experiment_id.cat_name),
                        experiment_usage.start_date,
                        experiment_usage.from_ip,
                        experiment_usage.coord_address.address,
                        experiment_usage.reservation_id,
                        experiment_usage.end_date
                )
            session.add(use)
            # TODO: The c.response of an standard command is an object with
            # a commandstring, whereas the response to an async command is 
            # a simple string to identify the request. The way in which the logger
            # currently handles these cases is somewhat shady.
            for c in experiment_usage.commands:
                # If we have a response, the c.response will be an object and not
                # a string. Generally, we will, unless the command was asynchronous
                # and it didn't finish executing.
                if type(c.response) != type(""):
                    session.add(Model.DbUserCommand(
                                    use,
                                    c.command.commandstring,
                                    c.timestamp_before,
                                    c.response.commandstring,
                                    c.timestamp_after
                                ))
                else:
                    # In this other case, the response is a string, which means
                    # that we have not updated it with the real response. Probably,
                    # it was an asynchronous command which did not finish executing
                    # by the time the experiment ended.
                    session.add(Model.DbUserCommand(
                                    use,
                                    c.command.commandstring,
                                    c.timestamp_before,
                                    "[RESPONSE NOT AVAILABLE]",
                                    c.timestamp_after
                                ))
            for f in experiment_usage.sent_files:
                session.add(Model.DbUserFile(
                                use,
                                f.file_sent,
                                f.file_hash,
                                f.timestamp_before,
                                f.file_info,
                                f.response.commandstring,
                                f.timestamp_after
                            ))

            for reservation_info_key in reservation_info:
                db_key = session.query(Model.DbUserUsedExperimentProperty).filter_by(name = reservation_info_key).first()
                if db_key is None:
                    db_key = Model.DbUserUsedExperimentProperty(reservation_info_key)
                    session.add(db_key)

                value = reservation_info[reservation_info_key]
                session.add(Model.DbUserUsedExperimentPropertyValue( str(value), db_key, use ))

            session.commit()
        finally:
            session.close()

    @logged()
    def finish_experiment_usage(self, reservation_id, end_date, last_command ):
        session = self.Session()
        try:
            user_used_experiment = session.query(Model.DbUserUsedExperiment).filter_by(reservation_id = reservation_id).first()
            if user_used_experiment is None:
                return False

            user_used_experiment.set_end_date(end_date)
            session.update(user_used_experiment)
            session.add(Model.DbUserCommand(
                            user_used_experiment,
                            last_command.command.commandstring,
                            last_command.timestamp_before,
                            last_command.response.commandstring,
                            last_command.timestamp_after
                        ))
            session.commit()
            return True
        finally:
            session.close()
  
    @logged()
    def append_command(self, reservation_id, command ):
        session = self.Session()
        try:
            user_used_experiment = session.query(Model.DbUserUsedExperiment).filter_by(reservation_id = reservation_id).first()
            if user_used_experiment is None:
                return False
            db_command = Model.DbUserCommand(
                            user_used_experiment,
                            command.command.commandstring,
                            command.timestamp_before,
                            command.response.commandstring if command.response is not None else None,
                            command.timestamp_after
                        )
            session.add(db_command)
            session.commit()
            return db_command.id
        finally:
            session.close()

    @logged()
    def update_command(self, command_id, response, end_timestamp ):
        session = self.Session()
        try:
            db_command = session.query(Model.DbUserCommand).filter_by(id = command_id).first()
            if db_command is None:
                return False

            db_command.response = response.commandstring
            db_command.set_timestamp_after(end_timestamp)
            session.update(db_command)
            session.commit()
            return True
        finally:
            session.close()

    @logged()
    def append_file(self, reservation_id, file_sent ):
        session = self.Session()
        try:
            user_used_experiment = session.query(Model.DbUserUsedExperiment).filter_by(reservation_id = reservation_id).first()
            if user_used_experiment is None:
                return False
            db_file_sent = Model.DbUserFile(
                            user_used_experiment,
                            file_sent.file_sent,
                            file_sent.file_hash,
                            file_sent.timestamp_before,
                            file_sent.file_info,
                            file_sent.response.commandstring if file_sent.response is not None else None,
                            file_sent.timestamp_after
                        )
            session.add(db_file_sent)
            session.commit()
            return db_file_sent.id
        finally:
            session.close()

    @logged()
    def update_file(self, file_id, response, end_timestamp ):
        session = self.Session()
        try:
            db_file_sent = session.query(Model.DbUserFile).filter_by(id = file_id).first()
            if db_file_sent is None:
                return False

            db_file_sent.response = response.commandstring
            db_file_sent.set_timestamp_after(end_timestamp)
            session.update(db_file_sent)
            session.commit()
            return True
        finally:
            session.close()

    @logged()
    def list_usages_per_user(self, user_login, first=0, limit=20):
        session = self.Session()
        try:
            user = self._get_user(session, user_login)
            uses = session.query(Model.DbUserUsedExperiment).filter_by(user=user).offset(first).limit(limit).all()
            return [ use.to_business_light() for use in uses ]
        finally:
            session.close()
    
    @logged()
    def retrieve_usage(self, usage_id):
        session = self.Session()
        try:
            use = session.query(Model.DbUserUsedExperiment).filter_by(id=usage_id).one()
            return use.to_business()
        finally:
            session.close()
            
    @admin_panel_operation
    @logged()
    def get_groups(self, user_login, parent_id=None):
        """ The user's permissions are not checked at the moment """
        
        def get_dto_children_recursively(groups):
            dto_groups = []
            for group in groups:
                dto_group = group.to_dto()
                if len(group.children) > 0:
                    dto_group.set_children(get_dto_children_recursively(group.children))
                dto_groups.append(dto_group)
            return dto_groups
        
        session = self.Session()
        try:
            groups = session.query(Model.DbGroup).filter_by(parent_id=parent_id).order_by(Model.DbGroup.name).all()
            dto_groups = get_dto_children_recursively(groups)
            return tuple(dto_groups)
        finally:
            session.close()
            
    @admin_panel_operation
    @logged()
    def get_users(self, user_login):
        """ Retrieves every user from the database """
        
        session = self.Session()
        try:
            users = session.query(Model.DbUser).all()
            # TODO: Consider sorting users.
            dto_users = [ user.to_dto() for user in users ]
            return tuple(dto_users)
        finally:
            session.close()
            
    @admin_panel_operation
    @logged()
    def get_roles(self, user_login):
        """ Retrieves every role from the database """
        session = self.Session()
        try:
            roles = session.query(Model.DbRole).all()
            dto_roles = [role.to_dto() for role in roles]
            return tuple(dto_roles)
        finally:
            session.close()
            

    @admin_panel_operation
    @logged()
    def get_experiments(self, user_login):
        """ All the experiments are returned by the moment """
        
        def sort_by_category_and_exp_name(exp1, exp2):
            if exp1.category.name != exp2.category.name:
                return cmp(exp1.category.name, exp2.category.name)
            else:
                return cmp(exp1.name, exp2.name)
            
        session = self.Session()
        try:
            experiments = session.query(Model.DbExperiment).all()
            experiments.sort(cmp=sort_by_category_and_exp_name)
            dto_experiments = [ experiment.to_dto() for experiment in experiments ]
            return tuple(dto_experiments)
        finally:
            session.close()

    @admin_panel_operation
    @logged()
    def get_experiment_uses(self, user_login, from_date, to_date, group_id, experiment_id, start_row, end_row, sort_by):
        """ All the experiment uses are returned by the moment. Filters are optional (they may be null), but if 
        applied the results should chang.e The result is represented as (dto_objects, total_number_of_registers) """

        session = self.Session()
        try:
            query_object = session.query(Model.DbUserUsedExperiment)

            # Applying filters

            if from_date is not None:
                query_object = query_object.filter(Model.DbUserUsedExperiment.end_date >= from_date)
            if to_date is not None:
                query_object = query_object.filter(Model.DbUserUsedExperiment.start_date <= to_date)
            if experiment_id is not None:
                query_object = query_object.filter(Model.DbUserUsedExperiment.experiment_id == experiment_id)

            if group_id is not None:
                def get_children_recursively(groups):
                    new_groups = groups[:]
                    for group in groups:
                        new_groups.extend(get_children_recursively(group.children))
                    return [ group for group in new_groups ]

                parent_groups = session.query(Model.DbGroup).filter(Model.DbGroup.id == group_id).all()
                group_ids = [ group.id for group in get_children_recursively(parent_groups) ]

                groups = session.query(Model.DbGroup).filter(Model.DbGroup.id.in_(group_ids)).subquery()
                users = session.query(Model.DbUser)
                users_in_group = users.join((groups, Model.DbUser.groups)).subquery()
                query_object = query_object.join((users_in_group, Model.DbUserUsedExperiment.user))
 
            # Sorting
            if sort_by is not None and len(sort_by) > 0:
                # Lists instead of sets, since the order of elements inside matters (first add Experiment, only then Category)
                tables_to_join = []
                sorters = []

                for current_sort_by in sort_by:
                    if current_sort_by in ('start_date','-start_date','end_date','-end_date','origin','-origin','id','-id'):
                        if current_sort_by.startswith('-'):
                            sorters.append(desc(getattr(Model.DbUserUsedExperiment, current_sort_by[1:])))
                        else:
                            sorters.append(getattr(Model.DbUserUsedExperiment, current_sort_by))

                    elif current_sort_by in ('agent_login', '-agent_login', 'agent_name', '-agent_name', 'agent_email', '-agent_email'):
                        tables_to_join.append((Model.DbUser, Model.DbUserUsedExperiment.user))
                        if current_sort_by.endswith('agent_login'):
                            sorter = Model.DbUser.login
                        elif current_sort_by.endswith('agent_name'):
                            sorter = Model.DbUser.full_name
                        else: # current_sort_by.endswith('agent_email')
                            sorter = Model.DbUser.email

                        if current_sort_by.startswith('-'):
                            sorters.append(desc(sorter))
                        else:
                            sorters.append(sorter)

                    elif current_sort_by in ('experiment_name', '-experiment_name'):
                        tables_to_join.append((Model.DbExperiment, Model.DbUserUsedExperiment.experiment))
                        if current_sort_by.startswith('-'):
                            sorters.append(desc(Model.DbExperiment.name))
                        else:
                            sorters.append(Model.DbExperiment.name)

                    elif current_sort_by in ('experiment_category', '-experiment_category'):
                        tables_to_join.append((Model.DbExperiment, Model.DbUserUsedExperiment.experiment))
                        tables_to_join.append((Model.DbExperimentCategory, Model.DbExperiment.category))
                        if current_sort_by.startswith('-'):
                            sorters.append(desc(Model.DbExperimentCategory.name))
                        else:
                            sorters.append(Model.DbExperimentCategory.name)

                while len(tables_to_join) > 0:
                    table, field = tables_to_join.pop(0)
                    # Just in case it was added twice, for instance if sorting by experiment name *and* category name
                    if (table,field) in tables_to_join:
                        tables_to_join.remove((table,field)) 
                    query_object = query_object.join((table, field))

                query_object = query_object.order_by(*sorters) # Apply all sorters in order


            # Counting

            total_number = query_object.count()

            if start_row is not None:
                starting = start_row
            else:
                starting = 0
            if end_row is not None:
                ending = end_row
            else:
                ending = total_number
            
            experiment_uses = query_object[starting:ending]

            dto_experiment_uses = [ experiment_use.to_dto() for experiment_use in experiment_uses ]
            return tuple(dto_experiment_uses), total_number
        finally:
            session.close()

    @logged()
    def get_user_permissions(self, user_login):
        session = self.Session()
        try:
            user = self._get_user(session, user_login)
            permission_types = session.query(Model.DbPermissionType).all()
            permissions = []
            for pt in permission_types:
                permissions.extend(self._gather_permissions(session, user, pt.name))
            dto_permissions = [ permission.to_dto() for permission in permissions ]
            return tuple(dto_permissions)
        finally:
            session.close()
    
    def _get_user(self, session, user_login):
        try:
            return session.query(Model.DbUser).filter_by(login=user_login).one()
        except NoResultFound:
            raise DbExceptions.DbProvidedUserNotFoundException("Unable to find a User with the provided login: '%s'" % user_login)
    
    def _get_experiment(self, session, exp_name, cat_name):
        try:
            return session.query(Model.DbExperiment) \
                        .filter(Model.DbExperimentCategory.name == cat_name) \
                        .filter_by(name=exp_name).one()
        except NoResultFound:
            raise DbExceptions.DbProvidedExperimentNotFoundException("Unable to find an Experiment with the provided unique id: '%s@%s'" % (exp_name, cat_name))
    
    def _gather_permissions(self, session, user, permission_type_name):
        permissions = []
        self._add_or_replace_permissions(permissions, self._get_permissions(session, user.role, permission_type_name))
        for group in user.groups:
            self._add_or_replace_permissions(permissions, self._get_permissions(session, group, permission_type_name))
        self._add_or_replace_permissions(permissions, self._get_permissions(session, user, permission_type_name))
        return permissions

    def _add_or_replace_permissions(self, permissions, permissions_to_add):
        permissions.extend(permissions_to_add)
        
    def _get_permissions(self, session, user_or_role_or_group_or_ee, permission_type_name):
        return [ pi for pi in user_or_role_or_group_or_ee.permissions if pi.get_permission_type().name == permission_type_name ]
    
    def _get_parameter_from_permission(self, session, permission, parameter_name, default_value = DEFAULT_VALUE):
        try:
            param = [ p for p in permission.parameters if p.get_name() == parameter_name ][0]
        except IndexError:
            if default_value == DEFAULT_VALUE:
                raise DbExceptions.DbIllegalStatusException(
                    permission.get_permission_type().name + " permission without " + parameter_name
                )
            else:
                return default_value
        return param.value
    
    def _get_float_parameter_from_permission(self, session, permission, parameter_name, default_value = DEFAULT_VALUE):
        value = self._get_parameter_from_permission(session, permission, parameter_name, default_value)
        try:
            return float(value)
        except ValueError:
            raise DbExceptions.InvalidPermissionParameterFormatException(
                "Expected float as parameter '%s' of '%s', found: '%s'" % (
                    parameter_name,
                    permission.get_permission_type().name,
                    value
                )
            )       

    def _get_int_parameter_from_permission(self, session, permission, parameter_name, default_value = DEFAULT_VALUE):
        value = self._get_parameter_from_permission(session, permission, parameter_name, default_value)
        try:
            return int(value)
        except ValueError:
            raise DbExceptions.InvalidPermissionParameterFormatException(
                "Expected int as parameter '%s' of '%s', found: '%s'" % (
                    parameter_name,
                    permission.get_permission_type().name,
                    value
                )
            )       
   
    def _get_bool_parameter_from_permission(self, session, permission, parameter_name, default_value = DEFAULT_VALUE):
        return self._get_parameter_from_permission(session, permission, parameter_name, default_value) 
    
    def _delete_all_uses(self):
        """ IMPORTANT: SHOULD NEVER BE USED IN PRODUCTION, IT'S HERE ONLY FOR TESTS """
        session = self.Session()
        try:
            uu = session.query(Model.DbUserUsedExperiment).all()
            for i in uu:
                session.delete(i)
            eu = session.query(Model.DbExternalEntityUsedExperiment).all()
            for i in eu:
                session.delete(i)
            session.commit()               
        finally:
            session.close()

    def _insert_user_used_experiment(self, user_login, experiment_name, experiment_category_name, start_time, origin, coord_address, reservation_id, end_date):
        """ IMPORTANT: SHOULD NEVER BE USED IN PRODUCTION, IT'S HERE ONLY FOR TESTS """
        session = self.Session()
        try:
            user = session.query(Model.DbUser).filter_by(login=user_login).one()
            category = session.query(Model.DbExperimentCategory).filter_by(name=experiment_category_name).one()
            experiment = session.query(Model.DbExperiment). \
                                    filter_by(name=experiment_name). \
                                    filter_by(category=category).one()
            experiment_id = experiment.id
            exp_use = Model.DbUserUsedExperiment(user, experiment, start_time, origin, coord_address, reservation_id, end_date)
            session.add(exp_use)
            session.commit()
            return experiment_id
        finally:
            session.close()
            
    def _insert_ee_used_experiment(self, ee_name, experiment_name, experiment_category_name, start_time, origin, coord_address, reservation_id, end_date):
        """ IMPORTANT: SHOULD NEVER BE USED IN PRODUCTION, IT'S HERE ONLY FOR TESTS """
        session = self.Session()
        try:
            ee = session.query(Model.DbExternalEntity).filter_by(name=ee_name).one()
            category = session.query(Model.DbExperimentCategory).filter_by(name=experiment_category_name).one()
            experiment = session.query(Model.DbExperiment). \
                                    filter_by(name=experiment_name). \
                                    filter_by(category=category).one()
            exp_use = Model.DbExternalEntityUsedExperiment(ee, experiment, start_time, origin, coord_address, reservation_id, end_date)
            session.add(exp_use)
            session.commit()
        finally:
            session.close()              
