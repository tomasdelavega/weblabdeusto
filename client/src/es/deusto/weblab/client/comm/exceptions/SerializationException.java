/*
* Copyright (C) 2005 onwards University of Deusto
* All rights reserved.
*
* This software is licensed as described in the file COPYING, which
* you should have received as part of this distribution.
*
* This software consists of contributions made by many individuals, 
* listed below:
*
* Author: Pablo Orduña <pablo@ordunya.com>
*
*/ 
package es.deusto.weblab.client.comm.exceptions;


public class SerializationException extends CommunicationException {
	private static final long serialVersionUID = -192687835688321030L;

	public SerializationException() {
	}

	public SerializationException(String arg0) {
		super(arg0);
	}

	public SerializationException(Throwable arg0) {
		super(arg0);
	}

	public SerializationException(String arg0, Throwable arg1) {
		super(arg0, arg1);
	}
}
