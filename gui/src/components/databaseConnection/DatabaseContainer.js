import React, { Component } from 'react';
import { Link } from 'react-router-dom';
import Button from 'react-bootstrap/Button';

class DatabaseContainer extends Component {
    constructor(props) {
        super(props);
        this.state = {
            formControls: {
                ipAddress: {
                    value: ''
                },
                name: {
                    value: ''
                },
                password: {
                    value: ''
                }
            },
            successMessage : ''
        }

        this.testConnection = this.testConnection.bind(this);
    }

    /*
    Currently using the handleSubmit method to try to establish a TCP connection with a database
         if the connection is successful, then show success message. Otherwise, show failure message and do
         not proceed to next screen
    */
    testConnection(event) {
        //currently assuming that connection will always be established, display that connection is successful for 3 seconds
        setTimeout(() => this.setState({ message: 'Connection Successful!' }), 3000);
    }

    setSuccessMessage(message) {
        this.setState({
            successMessage: message
        });
    }

    changeHandler = event => {

        const name = event.target.name;
        const value = event.target.value;

        this.setState({
            formControls: {
                ...this.state.formControls,
                [name]: {
                    ...this.state.formControls[name],
                    value
                }
            }
        });
    }


    render() {
        return (
            <div className="container">
                <div>
                    <h1> Database Connection </h1>
                    <p className="screenInfo"> Please fill the following fields to connect to a database to store data to</p>
                </div>
                <div class="text-center">
                    <form>
                        <div className="form-group">
                            <label>Host name: </label>
                            <input type="text"
                                name="ipAddress"
                                value={this.state.formControls.ipAddress.value}
                                onChange={this.changeHandler}
                            />
                        </div>

                        <div className="form-group">
                        <label>Username: </label>
                        <input type="text"
                            name="name"
                            value={this.state.formControls.name.value}
                            onChange={this.changeHandler}
                            />
                        </div>

                        <div className="form-group">
                        <label>Password: </label>
                        <input type="password"
                            name="password"
                            value={this.state.formControls.password.value}
                            onChange={this.changeHandler}
                            />
                        </div>
                    </form>
                </div>
                <Link to="/chooseNetwork">
                    <Button variant="primary" className="float-left footer-button">Back</Button>
                </Link>
                <Button variant="primary" className="float-right footer-button">Connect</Button>
            </div>
        );
    }

}


export default DatabaseContainer;