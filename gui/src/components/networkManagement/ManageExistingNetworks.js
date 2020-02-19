import React, { Component } from 'react';
import { Link } from 'react-router-dom';
import Button from 'react-bootstrap/Button';

const getAllNetworksBaseUrl = 'http://localhost:5000/chariot/api/v1.0/networks/all';
const xhr = new XMLHttpRequest();

class ManageExistingNetworks extends Component {
  constructor(props) {
    super(props);
    this.state = {
      existingNetworks: []
    }
  } 


  componentDidMount() {
    this.getExistingNetworks();
  }

  getExistingNetworks = () => {
    xhr.open('GET', getAllNetworksBaseUrl);
    xhr.setRequestHeader("Content-Type", "application/json");

    // Once a response is received
    xhr.onreadystatechange = () => {
      if (xhr.readyState === XMLHttpRequest.DONE) { // Once the request is done
        if (xhr.status === 200) {
          var responseJsonArray = JSON.parse(xhr.response); // Response is a dictionary 

          var updatedNetworksJsonArray = this.state.existingNetworks; 

          for (var i = 0; i < responseJsonArray.length; i++) {
            updatedNetworksJsonArray.push(responseJsonArray[i]);
          }

          this.setState({ existingNetworks: updatedNetworksJsonArray });
        }
      }
    }
    
    xhr.send();
  }

  // Create the links to settings for the gotten networks
  createNetworkLinks() {
    var networkLinks = [];

    for (var i = 0; i < this.state.existingNetworks.length; i++) {
      var curNetworkName = this.state.existingNetworks[i]["NetworkName"];
      var curNetworkDescription = this.state.existingNetworks[i]["Description"];
    
      // Create link for network
      networkLinks.push(
        <div key={i}>
          <Link className="link" to={"/" + curNetworkName + "/settings"}>{curNetworkName}</Link>: {curNetworkDescription}<br></br>
        </div>
      );

      // Now create links for network's corresponding devices
      for (var k = 0; k < this.state.existingNetworks[i]["Devices"].length; k++) {
        var curDeviceKey = curNetworkName + "Device" + k;
        var curDeviceName = this.state.existingNetworks[i]["Devices"][k];
        
        networkLinks.push(
          <div key={curDeviceKey}>
            <Link className="networksDeviceLink" to={"/" + curDeviceName + "/settings"}>{curDeviceName}</Link><br></br>
          </div>
        );
      }

    }

    return networkLinks;
  }

  render() {

    // ================================= Need a robust way of mapping the paths to network settings since they're all dynamic =================================
    return (
      <div className="container">
        <h1>Manage Existing Networks</h1>
        <p className="screenInfo">Select a network to modify its existing configuration settings.</p>
        
        {this.state.existingNetworks ? this.createNetworkLinks() : null}

        <Link to="/networkManager">
          <Button variant="primary" className="float-left footer-button">Back</Button> 
        </Link>
      </div>
    );
  }


}

export default ManageExistingNetworks; 