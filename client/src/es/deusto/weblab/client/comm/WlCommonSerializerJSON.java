/*
* Copyright (C) 2005-2009 University of Deusto
* All rights reserved.
*
* This software is licensed as described in the file COPYING, which
* you should have received as part of this distribution.
*
* This software consists of contributions made by many individuals, 
* listed below:
*
* Author: Pablo Orduña <pablo@ordunya.com>
*         Jaime Irurzun <jaime.irurzun@gmail.com>
*
*/

package es.deusto.weblab.client.comm;

import com.google.gwt.i18n.client.DateTimeFormat;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONException;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONParser;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import es.deusto.weblab.client.comm.exceptions.SerializationException;
import es.deusto.weblab.client.comm.exceptions.WlServerException;
import es.deusto.weblab.client.comm.exceptions.core.SessionNotFoundException;
import es.deusto.weblab.client.comm.exceptions.core.UserProcessingException;
import es.deusto.weblab.client.comm.exceptions.login.InvalidCredentialsException;
import es.deusto.weblab.client.comm.exceptions.login.LoginException;
import es.deusto.weblab.client.dto.SessionID;
import es.deusto.weblab.client.dto.experiments.Category;
import es.deusto.weblab.client.dto.experiments.Experiment;
import es.deusto.weblab.client.dto.users.ExternalEntity;
import es.deusto.weblab.client.dto.users.PermissionParameter;
import es.deusto.weblab.client.dto.users.Role;
import es.deusto.weblab.client.dto.users.User;

public class WlCommonSerializerJSON implements IWlCommonSerializer {

	public static final String ERR_CLIENT_INVALID_CREDENTIALS = "JSON:Client.InvalidCredentials";
	public static final String ERR_CLIENT_SESSION_NOT_FOUND = "JSON:Client.SessionNotFound";
	public static final String ERR_LOGIN_GENERAL = "JSON:Server.Login";
	public static final String ERR_UPS_GENERAL = "JSON:Server.UserProcessing";
	public static final String ERR_WEBLAB_GENERAL = "JSON:Server.WebLab";
	public static final String ERR_VOODOO_GENERAL = "JSON:Server.Voodoo";
	public static final String ERR_PYTHON_GENERAL = "JSON:Server.Python";

    public String serializeRequest(String method, JSONObject params){
		final JSONObject request = new JSONObject();
		request.put("params", params);
		request.put("method", new JSONString(method));
		return request.toString();
    }
    
	@Override
	public SessionID parseLoginResponse(String responseText)
			throws SerializationException, InvalidCredentialsException,
			LoginException, UserProcessingException, WlServerException {
				// "{\"result\": {\"id\": \"svAsc-rCIKLP1qeU\"}}"
				final JSONObject result = this.parseResultObject(responseText);
				final String sessionIdStr = this.json2string(result.get("id"));
				final SessionID sessionId = new SessionID(sessionIdStr);
				return sessionId;
			}

	@Override
	public String serializeLoginRequest(String username, String password)
			throws SerializationException {
				// {"params": {"username": "student1", "password": "password"}, "method": "login"}
				final JSONObject params = new JSONObject();
				params.put("username", new JSONString(username));
				params.put("password", new JSONString(password));
				return this.serializeRequest("login", params);
			}
	
    @Override
	public void parseLogoutResponse(String responseText)
	    throws SerializationException, WlServerException {
		this.parseResultObject(responseText);
    }
    
    @Override
	public String serializeLogoutRequest(SessionID sessionId) throws SerializationException {
		// {"params": {"session_id": {"id": "RqpLBRTlRW8ZVN1d"}}, "method": "logout"}
		final JSONObject params = new JSONObject();
		params.put("session_id", this.serializeSessionId(sessionId));
		return this.serializeRequest("logout", params);
    }
    
    @Override
	public User parseGetUserInformationResponse(String responseText)
    	throws SerializationException, SessionNotFoundException, UserProcessingException, WlServerException {
		//"{\"result\": {\"login\": \"student1\", \"email\": \"porduna@tecnologico.deusto.es\", 
		// \"full_name\": \"Name of student 1\", \"role\": {\"name\": \"student\"} }, \"is_exception\": false}"
		final JSONObject result = this.parseResultObject(responseText);
		
		return this.parseUser(result);
	}  

	@Override
	public String serializeGetUserInformationRequest(SessionID sessionId) throws SerializationException {
		final JSONObject params = new JSONObject();
		params.put("session_id", this.serializeSessionId(sessionId));
		return this.serializeRequest("get_user_information", params);
    }
    
    // General

    protected JSONObject serializeSessionId(SessionID sessionId) {
		final JSONObject session_id = new JSONObject();
		session_id.put("id", new JSONString(sessionId.getRealId()));
		return session_id;
    }
    
	private void throwException(JSONObject responseObject) throws WlServerException {
		// {"message": "No UserAuth found", "code": "JSON:Server.WebLab", "is_exception": true}
		final String faultCode = responseObject.get("code").isString().stringValue();
		final String faultString = responseObject.get("message").isString().stringValue();
		
		throw this.buildException(faultCode, faultString);
	}

	protected WlServerException buildException(final String faultCode, final String faultString) {
		if(faultCode.equals(WlCommonSerializerJSON.ERR_CLIENT_INVALID_CREDENTIALS)){
		    return new InvalidCredentialsException(faultString);
		}else if(faultCode.equals(WlCommonSerializerJSON.ERR_CLIENT_SESSION_NOT_FOUND)){
		    return new SessionNotFoundException(faultString);
		}else if(faultCode.equals(WlCommonSerializerJSON.ERR_LOGIN_GENERAL)){
		    return new LoginException(faultString);
		}else if(faultCode.equals(WlCommonSerializerJSON.ERR_UPS_GENERAL)){
		    return new UserProcessingException(faultString);
		}else if(faultCode.equals(WlCommonSerializerJSON.ERR_WEBLAB_GENERAL)){
		    return new WlServerException(faultString);
		}else if(faultCode.equals(WlCommonSerializerJSON.ERR_VOODOO_GENERAL)){
		    return new WlServerException(faultString);
		}else if(faultCode.equals(WlCommonSerializerJSON.ERR_PYTHON_GENERAL)){
		    return new WlServerException(faultString);
		}else{
		    return new WlServerException(faultString);    
		}
	}  
	
    protected PermissionParameter parsePermissionParameter(JSONObject jsonPermissionParameter) throws SerializationException {
    	return new PermissionParameter(
    			this.json2string(jsonPermissionParameter.get("name")),
    			this.json2string(jsonPermissionParameter.get("datatype")),
    			this.json2string(jsonPermissionParameter.get("value"))
    	);
	}	

    protected Role parseRole(JSONObject jsonRole) throws SerializationException {
    	final Role role = new Role();
    	role.setName(this.json2string(jsonRole.get("name")));
    	return role;
	}
    
    protected User parseUser(JSONObject jsonUser) throws SerializationException {
		final String login    = this.json2string(jsonUser.get("login"));
		final String email    = this.json2string(jsonUser.get("email"));
		final String fullName = this.json2string(jsonUser.get("full_name"));
		
	    final JSONValue roleValue = jsonUser.get("role");
	    if(roleValue == null)
	    	throw new SerializationException("Expected role field in User");
	    final JSONObject jsonRole = roleValue.isObject();
	    if(jsonRole == null)
	    	throw new SerializationException("Expected JSON Object as Role, found: " + roleValue);
	    final Role role = this.parseRole(jsonRole);
	    	    
		return new User(login, fullName, email, role);
	}

	protected ExternalEntity parseExternalEntity(JSONObject jsonExternalEntity) throws SerializationException {
		final int id = this.json2int(jsonExternalEntity.get("id"));
		final String name = this.json2string(jsonExternalEntity.get("name"));
		final String country = this.json2string(jsonExternalEntity.get("country"));
		final String description = this.json2string(jsonExternalEntity.get("description"));
		final String email = this.json2string(jsonExternalEntity.get("email"));
		
		return new ExternalEntity(id, name, country, description, email);
	}
	
	protected Experiment parseExperiment(JSONObject jsonExperiment) throws SerializationException {
	    final Experiment experiment = new Experiment();
	    
	    // id
	    final JSONValue jsonIdValue = jsonExperiment.get("id");
	    if(jsonIdValue == null)
	    	throw new SerializationException("Expected id field in Experiment");
	    experiment.setId(this.json2int(jsonIdValue));
	    
	    // name
	    final JSONValue jsonNameValue = jsonExperiment.get("name");
	    if(jsonNameValue == null)
	    	throw new SerializationException("Expected name field in Experiment");
	    experiment.setName(this.json2string(jsonNameValue));
	    
	    // category
	    final JSONValue jsonCategoryValue = jsonExperiment.get("category");
	    if(jsonCategoryValue == null)
	    	throw new SerializationException("Expected category field in Experiment");
	    final JSONObject jsonCategory = jsonCategoryValue.isObject();
	    if(jsonCategory == null)
	    	throw new SerializationException("Expected JSON Object as Category, found: " + jsonCategoryValue);
	    experiment.setCategory(new Category(this.json2string(jsonCategory.get("name"))));
	    
	    // startDate && endDate
	    final String startDateString = this.json2string(jsonExperiment.get("start_date"));
	    final String endDateString   = this.json2string(jsonExperiment.get("end_date"));
	    final DateTimeFormat formatter1 = DateTimeFormat.getFormat("yyyy-MM-dd");
	    final DateTimeFormat formatter2 = DateTimeFormat.getFormat("yyyy-MM-dd HH:mm:ss");
	    final DateTimeFormat formatter3 = DateTimeFormat.getFormat("yyyy-MM-ddTHH:mm:ss");
	    try {
			experiment.setStartDate(formatter1.parse(startDateString));
			experiment.setEndDate(formatter1.parse(endDateString));
	    } catch( final IllegalArgumentException iae ) {
			try{
			    experiment.setStartDate(formatter2.parse(startDateString));
			    experiment.setEndDate(formatter2.parse(endDateString));
			}catch(final IllegalArgumentException iae2){
				try{
				    experiment.setStartDate(formatter3.parse(startDateString));
				    experiment.setEndDate(formatter3.parse(endDateString));
				}catch(final IllegalArgumentException iae3){
				    throw new SerializationException("Couldn't parse date: " + startDateString + "; or: " + endDateString);
				}
			}
	    }
	    
	    return experiment;
	}
	
	protected JSONString parseResultString(String response) 
		throws SerializationException, WlServerException {
			final JSONValue result = this.parseResult(response);
			final JSONString resultString = result.isString();
			if(resultString == null)
			    throw new SerializationException("Expecting an string as a result; found: " + result);
			return resultString;
	}

	protected JSONObject parseResultObject(String response)
			throws SerializationException, WlServerException {
				final JSONValue result = this.parseResult(response);
				final JSONObject resultObject = result.isObject();
				if(resultObject == null)
				    throw new SerializationException("Expecting an object as a result; found: " + result);
				return resultObject;
			}

	protected JSONArray parseResultArray(String response)
			throws SerializationException, WlServerException {
				final JSONValue result = this.parseResult(response);
				final JSONArray resultArray = result.isArray();
				if(resultArray == null)
				    throw new SerializationException("Expecting an array as a result; found: " + result);
				return resultArray;
			}

	private JSONValue parseResult(String response) throws SerializationException,
			WlServerException {
				final JSONValue value;
				try {
				    value = JSONParser.parseStrict(response);
				} catch (final IllegalArgumentException e) {
				    throw new SerializationException("Invalid response: " + e.getMessage(), e);
				} catch (final JSONException e){
				    throw new SerializationException("Invalid response: " + e.getMessage(), e);
				}
				final JSONObject responseObject = value.isObject();
				if(responseObject == null)
				    throw new SerializationException("Expecting an object as a response; found: " + response);
				
				final JSONValue isException = responseObject.get("is_exception");
				final JSONBoolean isExceptionB = isException.isBoolean();
				if(isExceptionB.booleanValue())
				    this.throwException(responseObject);
				
				final JSONValue result = responseObject.get("result");
				if(result == null)
				    throw new SerializationException("Expecting 'result'; not found");
				return result;
			}

	protected String json2string(JSONValue value) throws SerializationException {
		return json2string(value, false);
	}
	
	protected String json2string(JSONValue value, boolean supportNull) throws SerializationException {
		if(value == null){
			if(supportNull)
				return null;
			
			throw new SerializationException("String expected, found null");
		}
		final JSONString jsonstring = value.isString();
		if(jsonstring == null)
		    throw new SerializationException("String expected, found: " + value);
		return jsonstring.stringValue();
	}

	protected boolean json2boolean(JSONValue value) throws SerializationException {
		if(value == null)
		    throw new SerializationException("Boolean expected, found null");
		final JSONBoolean jsonstring = value.isBoolean();
		if(jsonstring == null)
		    throw new SerializationException("Boolean expected, found: " + value);
		return jsonstring.booleanValue();
	}

	protected double json2double(JSONValue value) throws SerializationException {
		if(value == null)
		    throw new SerializationException("Double expected, found null");
		final JSONNumber jsonnumber = value.isNumber();
		if(jsonnumber == null)
		    throw new SerializationException("Double expected, found: " + value);
		return jsonnumber.doubleValue();
	}

	protected int json2int(JSONValue value) throws SerializationException {
		if(value == null)
		    throw new SerializationException("Int expected, found null");
		final JSONNumber jsonnumber = value.isNumber();
		if(jsonnumber == null)
		    throw new SerializationException("Int expected, found: " + value);
		return (int)jsonnumber.doubleValue();
	}
	
    @SuppressWarnings("unused")
	private boolean json2bool(JSONValue value) throws SerializationException {
		if(value == null)
		    throw new SerializationException("Boolean expected, found null");
		final JSONBoolean jsonboolean = value.isBoolean();
		if ( jsonboolean == null )
			throw new SerializationException("Boolean expected, found: " + value);
		return jsonboolean.booleanValue();
	}

}
