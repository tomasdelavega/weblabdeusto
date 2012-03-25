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

package es.deusto.weblab.client.experiments.visir;

import java.util.List;

import com.google.gwt.http.client.URL;

import es.deusto.weblab.client.comm.exceptions.CommException;
import es.deusto.weblab.client.configuration.IConfigurationRetriever;
import es.deusto.weblab.client.dto.experiments.ResponseCommand;
import es.deusto.weblab.client.lab.comm.callbacks.IResponseCommandCallback;
import es.deusto.weblab.client.lab.experiments.IBoardBaseController;
import es.deusto.weblab.client.lab.experiments.util.applets.AbstractExternalAppBasedBoard;
import es.deusto.weblab.client.lab.experiments.util.applets.flash.FlashExperiment;

public class VisirExperiment extends FlashExperiment {
	
	private boolean teacher = false;
	private String cookie = null;
	private String url = null;
	private String savedata = null;
	
	private List<String> circuitsAvailable;

	/**
	 * Constructs a Board for the Visir client. It does not actually generate the
	 * full HTML code until the experiment is started (and hence Start called), as
	 * it uses the WebLabFlashAppBasedBoard's deferred mode.
	 * 
	 * @param configurationRetriever
	 * @param boardController
	 */
	public VisirExperiment(IConfigurationRetriever configurationRetriever,
			IBoardBaseController boardController) {
		super(configurationRetriever, boardController, "", 800, 500,
				 "",
				 "Visir Flash Experiment", true);
	}
	
	@Override
	protected int getDefaultFlashTimeout() {
		return 60; // Increase the time for VISIR, since sometimes it becomes a high value
	}

	@Override
	protected String getDefaultFlashTimeoutMessage(String errorMessage) {
		return "Your web browser did not find VISIR code. If it's the first time you run it, this might be normal: it just means that it took too long to download VISIR; try to refresh WebLab and it will work. If this problem persists, contact the administrator. Error: " + errorMessage;
	}
	
	@Override
	public void end() {
		super.end();
	}

	@Override
	public void initialize() {
		super.initialize();
	}

	@Override
	public void setTime(int time) {
		super.setTime(time);
	}
	


	@Override
	public void start(final int time, final String initialConfiguration) {
		
		// The VISIR experiment now receives the initialization cookie it needs through
		// the new weblab API and its initialConfiguration parameter.
		final VisirSetupData initialConfig = new VisirSetupData();
		boolean success = initialConfig.parseData(initialConfiguration);
		if(success) {
			this.cookie            = initialConfig.getCookie();
			this.savedata          = initialConfig.getSaveData();
			this.url               = initialConfig.getURL();
			this.teacher           = initialConfig.isTeacher();
			this.circuitsAvailable = initialConfig.getCircuitsAvailable();
						
			this.updateFlashVars();
			this.setSwfFile(VisirExperiment.this.url);
			
			super.start(time, initialConfiguration);
		} else {
			System.out.println("Could not parse initial configuration: " + initialConfiguration);
		}
						
	}
		
	
	@Override
	public void onFlashReady() {
		initJavascriptAPI();
		if(this.circuitsAvailable.size() > 0)
			modifyFrame(this.generateCircuitsTableHTML());
	}
	
	public String generateCircuitsTableHTML() {
		final StringBuilder sb = new StringBuilder();
		
		sb.append("<div align='left'>\n");
		int circuitIndex = 1;
		for(final String circ : this.circuitsAvailable) {
			sb.append("<a href=\"\" OnClick=\"javascript:callOnLoadCircuit(");
			sb.append(circuitIndex);
			sb.append(");return false;\">");
			sb.append(circ);
			sb.append("</a><br>\n");
			circuitIndex++;
		}
		sb.append("<br><br></div>\n");
		
		return sb.toString();
	}

	
	private native void initJavascriptAPI() /*-{
		
		var that = this;
		
		$wnd.callOnLoadCircuit = $entry(function(id) {
			that.@es.deusto.weblab.client.experiments.visir.VisirExperiment::onLoadCircuit(I)(id);
		});
		
		$wnd.callRefresh = $entry(function() {
			that.@es.deusto.weblab.client.experiments.visir.VisirExperiment::refresh()();
		});
		
	}-*/;
	
	private native void modifyFrame(String circuitsTableHTML) /*-{
	
		var doc = $wnd.wl_iframe.contentDocument;
		if (doc == undefined || doc == null)
	    	doc = $wnd.wl_iframe.contentWindow.document;
	    	
	    // TODO: Internationalize "Circuits available"
	 	$doc.getElementById('div_extra').innerHTML = "<div align='left'><font color='black'><b><h2>Circuits available</h2></b></font></div>" + circuitsTableHTML;
	}-*/;
	

	private void refresh() {
		//this.savedata = "<save><instruments list=\"breadboard/breadboard.swf|multimeter/multimeter.swf|functiongenerator/functiongenerator.swf|oscilloscope/oscilloscope.swf|tripledc/tripledc.swf\"/><circuit><circuitlist><component>W 255 442 234 457.15 279.5 442 325</component></circuitlist></circuit></save>";
		this.updateFlashVars();
		this.refreshFlash();
	}
	
	private void onLoadCircuit(final int id) {
		//System.out.println("[DBG] Should load circuit number: " + id);
		
		assert(id > 0);
		
		// Get the circuit name from the internal list
		final String circuitName = this.circuitsAvailable.get(id - 1);
		
		// Build the command to request the data for the specified circuit.
		final VisirCircuitDataRequestCommand reqData = new VisirCircuitDataRequestCommand(circuitName);
		
		// Send the request and process the response.
		AbstractExternalAppBasedBoard.staticBoardController.sendCommand(reqData, 
				new IResponseCommandCallback() {

					@Override
					public void onSuccess(ResponseCommand responseCommand) {
						
						final String circuitData = responseCommand.getCommandString();
						
						// Change the current circuit to the specified one.
						VisirExperiment.this.changeCircuit(id, circuitName, circuitData);
					}

					@Override
					public void onFailure(CommException e) {
						System.out.println("Error: Could not retrieve circuit data");
					}
					
				});
	}
	


	/**
	 * Changes the active VISIR circuit to the specified one.
	 * @param id Local identifier of the circuit, as determined by the in-screen circuit list.
	 * @param circuitName Name of the circuit.
	 * @param circuitData Data of the circuit.
	 */
	protected void changeCircuit(int id, String circuitName, String circuitData) {
		//System.out.println("[DBG] Changing circuit");
		this.savedata = circuitData.trim();
		//this.savedata = "<save><instruments list=\"breadboard/breadboard.swf|multimeter/multimeter.swf|functiongenerator/functiongenerator.swf|oscilloscope/oscilloscope.swf|tripledc/tripledc.swf\"/><circuit><circuitlist><component>W 255 442 234 457.15 279.5 442 325</component></circuitlist></circuit></save>";
		this.updateFlashVars();
		this.refresh();
	}

	/**
	 * Will set or update the flash vars with local parameters such as cookie or savedata.
	 * These parameters should be set beforehand. Flashvars updates have no effect once the iframe containing
	 * the flash object has been populated.
	 * Note that savedata is assumed to be URL-encoded.
	 */
	protected void updateFlashVars() {
		//final String testsavedata = "<save><instruments+list=\"breadboard/breadboard.swf|multimeter/multimeter.swf|functiongenerator/functiongenerator.swf|oscilloscope/oscilloscope.swf|tripledc/tripledc.swf\"+/><multimeter+/><circuit><circuitlist><component>R+1.6k+52+26+0</component><component>R+2.7k+117+26+0</component><component>R+10k+182+78+0</component><component>R+10k+182+52+0</component><component>R+10k+182+26+0</component><component>C+56n+247+39+0</component><component>C+56n+247+91+0</component></circuitlist></circuit></save>&amp;http=1<save><instruments+list=\"breadboard/breadboard.swf|multimeter/multimeter.swf|functiongenerator/functiongenerator.swf|oscilloscope/oscilloscope.swf|tripledc/tripledc.swf\"+/><multimeter+/><circuit><circuitlist><component>R+1.6k+52+26+0</component><component>R+2.7k+117+26+0</component><component>R+10k+182+78+0</component><component>R+10k+182+52+0</component><component>R+10k+182+26+0</component><component>C+56n+247+39+0</component><component>C+56n+247+91+0</component></circuitlist></circuit></save>";
		
		String flashvars = "teacher=" + (this.teacher?"1":"0");
		if(this.cookie != "")
			flashvars += "&cookie="+this.cookie;
		if(this.savedata != "")
			flashvars += "&savedata="+URL.encode(this.savedata);
		
		// Data is received encoded, and used to generate the website straightaway.
		//final String flashvars = "cookie="+this.cookie+"&savedata="+this.savedata;
		
		//System.out.println(this.savedata);
		//System.out.println(URL.decodeComponent(this.savedata));
		
		this.setFlashVars(flashvars);
	}

}
