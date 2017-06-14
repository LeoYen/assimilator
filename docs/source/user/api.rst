.. _api:

API
===

The juice of Assimilator relies on the /api. From here one can access all Firewall configuration, check rules, routes and network objects. Also the user can test an access to see if the Firewall grants the access. Assimilator has default resource URL for all firewalls (like rules, objects and routes) and private resource URL destined for each Firewall brand. This is to grasp the full functionality of Firewalls.

Config
------

**/api/<firewall>/config**

Gets the full configuration of the Firewall, in it's native format. In many cases this is XML.

*Example*

::
	
	GET /api/argentina/config
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json

::

	200 OK

.. block-code: json
   
   {
   		"config" : " ... "
   }


Rules
-----

**/api/<firewall>/rules**

Get all rules in the selected Firewall. This can be filtered with URL arguments.

*Example (PaloAlto)*

::
	
	GET /api/argentina/rules
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json

::

	200 OK

.. block-code: json

   {
   		"rules" : [
   		{
	      "log-end": false,
	      "qos": {
	        "marking": null,
	        "type": null
	      },
	      "negate-source": false,
	      "disabled": true,
	      "rule-type": "universal",
	      "tag": [],
	      "log-start": false,
	      "hip-profiles": [],
	      "negate-destination": false,
	      "description": null,
	      "category": [
	        "any"
	      ],
	      "from": [
	        "trust"
	      ],
	      "service": [
	        "any"
	      ],
	      "source": [
	        "any"
	      ],
	      "destination": [
	        "8.8.8.8",
	        "8.8.4.4"
	      ],
	      "application": [
	        "dns"
	      ],
	      "profile-setting": null,
	      "log-setting": null,
	      "to": [
	        "untrust"
	      ],
	      "schedule": null,
	      "source-user": [
	        "any"
	      ],
	      "icmp-unreachable": false,
	      "name": "DNS Google Access",
	      "disable-server-response-inspection": false,
	      "action": "allow"
	    },
	    ...
   		]
   }

*Example with arguments (PaloAlto)*

::
	
	GET /api/argentina/rules?from=dmz&to=untrust
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json

::

	200 OK

.. block-code: json

   {
   		"rules" : [
   		{
	      "log-end": true,
	      "qos": {
	        "marking": null,
	        "type": null
	      },
	      "negate-source": false,
	      "disabled": true,
	      "rule-type": "universal",
	      "tag": [],
	      "log-start": false,
	      "hip-profiles": [],
	      "negate-destination": false,
	      "description": null,
	      "category": [
	        "any"
	      ],
	      "from": [
	        "dmz"
	      ],
	      "service": [
	        "any"
	      ],
	      "source": [
	        "any"
	      ],
	      "destination": [
	        "10.10.50.2",
	      ],
	      "application": [
	        "web-browsing",
	        "ssl"
	      ],
	      "profile-setting": null,
	      "log-setting": null,
	      "to": [
	        "untrust"
	      ],
	      "schedule": null,
	      "source-user": [
	        "any"
	      ],
	      "icmp-unreachable": false,
	      "name": "Internet access",
	      "disable-server-response-inspection": false,
	      "action": "allow"
	    },
	    ...
   		]
   }


To add a rule one simply change the method to POST and sends one of these JSON objects in the body of the request.

::
	
	POST /api/brasil/rules
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json
	{
		"log-end": true,
		"qos": {
			"marking": null,
			"type": null
		},
		"negate-source": false,
		"disabled": true,
		"rule-type": "universal",
		"tag": [],
		"log-start": false,
		"hip-profiles": [],
		"negate-destination": false,
		"description": null,
		"category": [
			"any"
		],
		"from": [
			"dmz"
		],
		"service": [
			"any"
		],
		"source": [
			"any"
		],
		"destination": [
			"10.10.50.2",
		],
		"application": [
			"web-browsing",
			"ssl"
		],
		"profile-setting": null,
		"log-setting": null,
		"to": [
			"untrust"
		],
		"schedule": null,
		"source-user": [
			"any"
		],
		"icmp-unreachable": false,
		"name": "Internet access",
		"disable-server-response-inspection": false,
		"action": "allow"
	}

To delete a rule, use DELETE.

::
	
	POST /api/brasil/rules
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json
	{
		"name" : "Some Rule Name"
	}

To replace rules values use PUT, here we **replace** the values of 'source' with new values.

::
	
	POST /api/brasil/rules
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json
	{
		"name" : "Some Rule Name",
		"source" : 
		{
			"192.168.1.50",
			"192.168.1.40"
		}
	}

To append new objects to a rule use PATCH, here we **add** objects to destination.

::
	
	POST /api/brasil/rules
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json
	{
		"name" : "Some Rule Name",
		"destination" : 
		{
			"100.200.100.10"
		}
	}

Match
-----

**/api/<firewall>/rules/match**

A very useful resource is match. With it one can test a source, destination and port to check if the Firewall allows that connection. Many Firewalls already have this funcionality, other don't (AWS). What they lack is the ease of use. Assimilator only requires source, destination and port (optionally a protocol), other required input by the Firewalls (such as dmz zones) are resolved by Assimilator either through route tables or configuration.
If the access is granted then it returns the rule that allows it.

::
	
	GET /api/uruguay/rules/match?source=192.168.4.5&destination=100.150.100.150&port=443
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json

::

	200 ok

.. block-code: json

   {

   }


Objects
-------

**/api/<firewall>/objects/<address|address-group|service|service-group>**

Firewall objects identify hosts and ports in the rules, basically there are four type of objects:

 * Address: Hosts identified by an IP, IP range, subnet or FQDN.
 * Service: A combination of protocol and source/destination port.
 * Address Group: A group of Address objects.
 * Service Group: A group of service objects.

With Assimilator one can create/modify/delete objects easily.

::
	
	POST /api/chile/objects/address
	key: BDP0NyHZMDfz98kcmD3GuBIQGW9EZTgWGPf56dWnkD3LGM3dZPaZICrKVnTnQWh5YdGLh5SJ9ktg7ReR4le94zyxdigdLTHHf8s
	Content-Type: application/json
	{
		"name" : "Corp_DNS",

	}



Routes
------

**/api/<firewall>/route**

