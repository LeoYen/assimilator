from flask_restful import Resource
from flask import request,abort,jsonify,Response
from bs4 import BeautifulSoup
from app.modules.firewall import Firewall
from functools import wraps
from lxml import etree
from lxml.builder import E
from bs4.element import Tag
from bs4 import BeautifulSoup as BS
from jnpr.junos import Device
from jnpr.junos.exception import ConnectError
import logging, socket, json, os

#Get logger
logger = logging.getLogger(__name__)

logging.getLogger("ncclient").setLevel(logging.ERROR)

class JUNOS(Firewall):
	def __init__(self,firewall_config):
		self.firewall_config = firewall_config
		if self.firewall_config['privatekey'] and self.firewall_config['privatekeypass']:
			#RSA SSH connection
			logger.info("Juniper RSA SSH connection.")
			self.dev = Device(host=self.firewall_config['primary'], passwd=self.firewall_config['privatekeypass'],\
								ssh_private_key_file=self.firewall_config['privatekey'],user=self.firewall_config['user'],\
								port=self.firewall_config['port'], gather_facts=False)
		else:
			#User password connection
			logger.info("Juniper User/Password connection.")
			self.dev = Device(host=self.firewall_config['primary'], password=self.firewall_config['pass'],\
								user=self.firewall_config['user'], port=self.firewall_config['port'], gather_facts=False)
		self.dev.open(normalize=True)
		try:
			self.dev.timeout = int(self.firewall_config['timeout']) if self.firewall_config['timeout'] else 15
		except ValueError:
			logger.warning("Firewall timeout is not an int, setting default value.")
			self.dev.timeout = 15
		self.primary = self.firewall_config['primary']

class configuration(JUNOS):
	def get(self):
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 502
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		ret = self.dev.rpc.get_config()
		self.dev.close()

		return {'config' : etree.tostring(ret, encoding='unicode')}
class rules(JUNOS):
	def get(self,args):
		logger.debug("class rules(JUNOS).get({0})".format(str(args)))
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		soup = BS(str(etree.tostring(self.dev.rpc.get_firewall_policies(), encoding='unicode')),'xml')
		logger.debug("soup: " + str(soup))
		logger.debug("Closing device...")
		self.dev.close()
		entries = list()
		for context in soup.find("security-policies").children:			
			if type(context) != Tag:
				continue
			elif context.name == "default-policy":
				continue
			else:
				logger.debug("context: {0}".format(str(context)))
			src_zone = context.find("context-information").find("source-zone-name").text
			dst_zone = context.find("context-information").find("destination-zone-name").text
			logger.debug("src_zone: {0}\ndst_zone: {1}\n".format(src_zone,dst_zone))
			for rule in context.children:
				logger.debug("Rule: {0}".format(str(rule)))
				if rule.name == "context-information" or type(rule) != Tag:
					continue
				aux = {
					"enabled" : True if rule.find('policy-state').text == 'enabled' else False,
					"id" : int(rule.find('policy-identifier').text),
				      "action": rule.find('policy-information').find('policy-action').find('action-type').text,
				      "destination": list(),
				      "from": src_zone,
				      "logging": False if rule.find('policy-information').find('policy-action').find('log') else rule.find('policy-information').find('policy-action').find('log'),
				      "name": rule.find('policy-information').find('policy-name').text,
				      "application": list(),
				      "source": list(),
					"to": dst_zone
		   		 	}
				for addr in rule.find('source-addresses').children:
					if type(addr) != Tag:
						continue
					aux['source'].append(addr.find('address-name').text)
				for addr in rule.find('destination-addresses').children:
					if type(addr) != Tag:
						continue
					aux['destination'].append(addr.find('address-name').text)
				for addr in rule.find('applications').children:
					if type(addr) != Tag:
						continue
					aux['application'].append(addr.find('application-name').text)
				entries.append(aux)
		#entries = self.filter(args,entries)
		return {'len' : len(entries), 'rules' : entries}
	def post(self,data):
		logger.debug("class rules(JUNOS).post({0})".format(str(data)))
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		self.dev.bind(cu=Config)
		soup = BS(str(etree.tostring(self.dev.rpc.get_firewall_policies(policy_name = data['name']), encoding='unicode')),'xml')
		if soup.find("security-policies").text.strip('\n'):
			logger.warning("Existing policy.")
			return {'error' : 'Rule already exists.'}, 409
		else:
			logger.debug("Policy absent, creating new policy.")
		xml = """<configuration><security><policies><policy><from-zone-name>{0}</from-zone-name><to-zone-name>{1}</to-zone-name><policy><name>{2}</name>
				<match>{3}</match><then><permit></permit><count></count></then></policy></policy></policies></security></configuration>"""
		try:
			self.dev.cu.lock()
		except LockError:
			logger.error("Configuration locked.")
			self.dev.close()
			return {'error' : 'Could not lock configuration.'}, 504
		else:
			logger.info("Locked configuration.")
		xml_source = ''
		xml_destination = ''
		xml_app = ''
		for source in data['source']:
			xml_source += '<source-address>{0}</source-address>'.format(source)
		for destination in data['destination']:
			xml_destination += '<destination-address>{0}</destination-address>'.format(destination)
		for application in data['application']:
			xml_application += '<application-address>{0}</application-address>'.format(application)
		try:
			logger.debug("Loading configuration to device.")
			self.dev.cu.load(xml.format(data['form'],data['to'],data['name'],xml_source+xml_destination+xml_application),format='xml',merge=True)
		except ConfigLoadError as e:
			logger.error("Unable to load configuration: {0}".str(e))
			logger.info("Unlocking configuration...")
			try:
				self.dev.cu.unlock()
			except UnlockError as err:
				logger.error("Unable to unlock configuration: {0}".format(str(err)))
				return {'error' : "Unable to load and unlock configuration: {0}".format(str(err))}, 500
			else:
				logger.info("Configuration unlocked.")
			finally:
				logger.info("Closing connection...")
				self.dev.close()
			return {'error' : "Unable to load configuration: {0}".str(e)}, 500
		else:
			logger.info("Unlocking configuration...")
			try:
				self.dev.cu.unlock()
			except UnlockError as err:
				logger.error("Unable to unlock configuration: {0}".format(str(err)))
				return {'error' : "Unable to load and unlock configuration: {0}".format(str(err))}, 500
			else:
				logger.info("Configuration unlocked.")
				return data, 201
	def patch(self,name,data):
		logger.debug("class rules(JUNOS).patch({0})".format(str(data)))
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		self.dev.bind(cu=Config)
		soup = BS(str(etree.tostring(self.dev.rpc.get_firewall_policies(policy_name = name), encoding='unicode')),'xml')
		if not soup.find("security-policies").text.strip('\n'):
			logger.error("Policy absent, cannot patch objects to rule.")
			return {'error' : 'Rule does not exists.'}, 404
		else:
		xml = """<configuration><security><policies><policy><from-zone-name>{0}</from-zone-name><to-zone-name>{1}</to-zone-name><policy><name>{2}</name>
				<match>{3}</match></policy></policy></policies></security></configuration>"""
		try:
			self.dev.cu.lock()
		except LockError:
			logger.error("Configuration locked.")
			self.dev.close()
			return {'error' : 'Could not lock configuration.'}, 504
		else:
			logger.info("Locked configuration.")
		xml_source = ''
		xml_destination = ''
		xml_app = ''
		for source in data['source']:
			xml_source += '<source-address>{0}</source-address>'.format(source)
		for destination in data['destination']:
			xml_destination += '<destination-address>{0}</destination-address>'.format(destination)
		for application in data['application']:
			xml_application += '<application-address>{0}</application-address>'.format(application)
		try:
			logger.debug("Loading configuration to device.")
			self.dev.cu.load(xml.format(data['form'],data['to'],data['name'],xml_source+xml_destination+xml_application),format='xml',merge=True)
		except ConfigLoadError as e:
			logger.error("Unable to load configuration: {0}".str(e))
			logger.info("Unlocking configuration...")
			try:
				self.dev.cu.unlock()
			except UnlockError as err:
				logger.error("Unable to unlock configuration: {0}".format(str(err)))
				return {'error' : "Unable to load and unlock configuration: {0}".format(str(err))}, 500
			else:
				logger.info("Configuration unlocked.")
			finally:
				logger.info("Closing connection...")
				self.dev.close()
			return {'error' : "Unable to load configuration: {0}".str(e)}, 500
		else:
			logger.info("Unlocking configuration...")
			try:
				self.dev.cu.unlock()
			except UnlockError as err:
				logger.error("Unable to unlock configuration: {0}".format(str(err)))
				return {'error' : "Unable to load and unlock configuration: {0}".format(str(err))}, 500
			else:
				logger.info("Configuration unlocked.")
				return data, 200

class objects(JUNOS):
	def get(self,args=None,object=None):
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		entries = list()
		if object == "address":
			filter = E('security',E('zones'))
			rpc = etree.tostring(self.dev.rpc.get_config(filter), encoding='unicode')
			self.dev.close()
			soup = BS(str(rpc),'xml')
			for zone in soup.zones.children:
				if type(zone) != Tag or not zone.find('address-book'):
					continue
				dmz = zone.find('name').text
				for obj in zone.find('address-book').children:
					if type(obj) != Tag or obj.name != "address":
						continue
					aux = {
						'dmz' : dmz,
						'type' : 'ip' if obj.find('ip-prefix') else 'hostname',
						'name' : obj.find('name').text,
						'value' : obj.find('ip-prefix').text if obj.find('ip-prefix') else obj.find('dns-name').text
						}
					entries.append(aux)
		elif object == "service":
			filter = E('applications')
			rpc = etree.tostring(self.dev.rpc.get_config(filter), encoding='unicode')
			self.dev.close()
			soup = BS(str(rpc),'xml')
			for application in soup.applications.children:
				if type(application) != Tag or application.name != 'application':
					continue
				aux = {
				'name' : application.find('name').text,
				'protocol' : application.protocol.text if application.protocol else '',
				'port' : application.find('destination-port').text if application.find('destination-port') else ''
				}
				entries.append(aux)
			#Load default junos service objects
			with open(os.path.join(os.path.dirname(__file__), 'default-applications.json')) as f:
				for app in json.loads(f.read())['list']:
					if not request.args:
						entries.append(app)
					else:
						for opcion in request.args:
							if opcion in app.keys():
								if type(app[opcion]) == list:
									for i in app[opcion]:
										if request.args[opcion].lower() in i.lower():
											entries.append(app)
								elif request.args[opcion].lower() in app[opcion].lower():
									entries.append(app)
		elif object == "address-group":
			filter = E('security',E('zones'))
			rpc = etree.tostring(self.dev.rpc.get_config(filter), encoding='unicode')
			self.dev.close()
			soup = BS(str(rpc),'xml')
			for zone in soup.zones.children:
				if type(zone) != Tag or not zone.find('address-book'):
					continue
				dmz = zone.find('name').text
				for obj in zone.find('address-book').children:
					if type(obj) != Tag or obj.name != "address-set":
						continue
					aux = {
					'dmz' : dmz,
					'name' : obj.find('name').text,
					'members' : list()
					}
					for addr in obj.children:
						if type(addr) != Tag or addr.name == "name":
							continue
						aux['members'].append(addr.find('name').text)
					entries.append(aux)
		elif object == "service-group":
			filter = E('applications')
			rpc = etree.tostring(self.dev.rpc.get_config(filter), encoding='unicode')
			self.dev.close()
			soup = BS(str(rpc),'xml')
			for application in soup.applications.children:
				if type(application) != Tag or application.name != 'application-set':
					continue
				aux = {
				'name' : application.find('name').text,
				'members' : list()
				}
				for member in application.children:
					if type(member) != Tag or member.name == 'name':
						continue
					aux['members'].append(member.find('name').text)
				entries.append(aux)
		else:
			logger.warning("Resource not found.")
			return {'error' : 'Resource not found.'}, 404
		entries = self.filter(args,entries)
		return {'firewall' : self.firewall_config['name'], 'len' : len(entries), str(object) : entries}
class route(JUNOS):
	def get(self):
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		
		rpc = etree.tostring(str(self.dev.rpc.get_route_information()), encoding='unicode')
		soup = BS(str(rpc).replace('\n            ','').replace('\n',''),'xml')
		self.dev.close()
		logger.debug(str(soup))
		return {'route' : {
					'destination' : soup.find('rt-destination').text,
					'active' : True if soup.find('current-active') else False,
					'type' : soup.find('protocol-name').text,
					'preference' : int(soup.preference.text),
					'age' : soup.age.text,
					'next-hop' : soup.to.text,
					'interface' : soup.via.text
					}}
class route_ip(JUNOS):
	def get(self,ip):
		try:
			socket.inet_aton(str(ip))
		except TypeError:
			#Not a valid IP
			logger.warning("Not a valid IP.")
			logger.debug("ip: {0}".format(str(ip)))
			return {'error' : 'Not a valid IP.'}, 400
		else:
			if not self.dev.connected:
				logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
				return {'error' : 'Could not connect to device.'}, 504
			else:
				logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
			rpc = etree.tostring(self.dev.rpc.get_route_information(destination=request.args['ip']), encoding='unicode')
			soup = BS(u''.join(rpc).encode('utf-8'),'xml')
			rpc2 = etree.tostring(self.dev.rpc.get_interface_information(interface_name=soup.find('via').text), encoding='unicode')
			self.dev.close()
			soup2 = BS(u''.join(rpc2).encode('utf-8'),'xml')			
			return {'route' : {
						'destination' : soup.find('rt-destination').text if soup.find('rt-destination') else None,
						'active' : True if soup.find('current-active') else False,
						'type' : soup.find('protocol-name').text if soup.find('protocol-name') else None,
						'preference' : int(soup.preference.text) if soup.preference else None,
						'age' : soup.age.text if soup.age else None,
						'next-hop' : soup.to.text if soup.to else None,
						'interface' : soup.via.text if soup.via else None,
						'zone' : soup2.find('logical-interface-zone-name').text.replace('\n','')
						}}
class match(JUNOS):
	def get(self,args):
		logger.debug("Juniper.match.get()")
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		#Source Zone
		if 'from' in args:
			from_zone = args['from']
		else:
			rpc = etree.tostring(self.dev.rpc.get_route_information(destination=args['source']), encoding='unicode')
			soup = BS(u''.join(rpc).encode('utf-8'),'xml')
			rpc = etree.tostring(self.dev.rpc.get_interface_information(interface_name=soup.find('via').text), encoding='unicode')
			soup = BS(u''.join(rpc).encode('utf-8'),'xml')
			from_zone = soup.find('logical-interface-zone-name').text.replace('\n','')
		#Destination Zone
		if 'to' in args:
			to_zone = args['to']
		else:
			rpc = etree.tostring(str(self.dev.rpc.get_route_information(destination=args['destination'])), encoding='unicode')
			soup = BS(u''.join(rpc).encode('utf-8'),'xml')
			rpc = etree.tostring(str(self.dev.rpc.get_interface_information(interface_name=soup.find('via').text)), encoding='unicode')
			soup = BS(u''.join(rpc).encode('utf-8'),'xml')
			to_zone = soup.find('logical-interface-zone-name').text.replace('\n','')

		if to_zone == from_zone:
			return {'allowed' : True, 'policy' : 'Intrazone'}
		rpc = str(self.dev.rpc.match_firewall_policies(
			from_zone=from_zone,
			to_zone=to_zone,
			source_ip=args['source'],
			destination_ip=args['destination'],
			source_port=args['source-port'] if 'source-port' in args else "1025",
			destination_port=args['port'],
			protocol=args['protocol'] if 'protocol' in args else "tcp"
			))
		self.dev.close()
		soup = BS(rpc,'xml')
		try:
			aux = {
				"enabled" : True if soup.find('policy-state').text == 'enabled' else False,
				"id" : int(soup.find('policy-identifier').text),
			    "action": soup.find('policy-information').find('policy-action').find('action-type').text,
			    "destination": list(),
			    "from": soup.find('context-information').find('source-zone-name').text,
			    "logging": False if soup.find('policy-information').find('policy-action').find('log') else soup.find('policy-information').find('policy-action').find('log'),
			    "name": soup.find('policy-information').find('policy-name').text,
			    "application": list(),
			    "source": list(),
				"to": soup.find('context-information').find('destination-zone-name').text
	   		 	}
			for addr in soup.find('source-addresses').children:
				if type(addr) != Tag:
					continue
				aux['source'].append(addr.find('address-name').text)
			for addr in soup.find('destination-addresses').children:
				if type(addr) != Tag:
					continue
				aux['destination'].append(addr.find('address-name').text)
			for addr in soup.find('applications').children:
				if type(addr) != Tag:
					continue
				aux['application'].append(addr.find('application-name').text)
		except:
			aux = {
			"enabled" : True if soup.find('policy-state').text == 'enabled' else False,
			"id" : int(soup.find('policy-identifier').text),
			"action": soup.find('policy-information').find('policy-action').find('action-type').text,
			"name": soup.find('policy-information').find('policy-name').text,
			}
		return {'allowed' : True if soup.find('policy-action').find('action-type').text == "permit" else False, 'policy' : aux}
class objects(JUNOS):
	def get(self):
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		rpc = etree.tostring(str(jns.rpc.get_commit_information()), encoding='unicode')
		soup = BS(rpc,'xml')
		entries = list()
		for entry in soup.find('commit-information').children:
			if type(entry) != Tag:
				continue
			entries.append({'user' : entry.user.text, 'sequence' : entry.find('sequence-number').text, 'date' : entry.find('date').text, 'comment' : entry.log.text})
		return {'len' : len(entries), 'commit' : entries}
	def post(self,comment):
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		self.dev.bind(cu=Config)
			self.dev.cu.lock()
		except LockError:
			logger.error("Configuration locked.")
			self.dev.close()
			return {'error' : 'Could not lock configuration.'}, 504
		else:
			logger.info("Locked configuration.")
		try:
			if comment:
				self.dev.cu.commit(comment=comment)
			else:
				self.dev.cu.commit()
		except CommitError:
			logger.error("Unable to commit.")
			try:
				logger.info("Unlocking configuration...")
				self.dev.cu.unlock()
			except UnlockError:
				logger.error("Unable to unlock configuration: {0}".format(str(err)))
				return {'error' : 'Unable to commit and unlock configuration.'}, 504
			else:
				logger.info("Configuration unlocked.")
				return {'error' : 'Unable to commit.'}, 504
		else:
			logger.info("Configuration commited successfully.")
			logger.info("Unlocking configuration...")
			try:
				self.dev.cu.unlock()
			except UnlockError:
				logger.error("Unable to unlock configuration: {0}".format(str(err)))
				return {'error' : 'Configuration commited but cannot unlock configuration.'}, 504
			else:
				logger.info("Configuration unlocked.")
				return {'commit' : 'success'}
		finally:
			logger.info("Closing connection...")
			self.dev.close()

class hitcount(JUNOS):
	def get(self):
		if not self.dev.connected:
			logger.error("{0}: Firewall timed out or incorrect device credentials.".format(self.firewall_config['name']))
			return {'error' : 'Could not connect to device.'}, 504
		else:
			logger.info("{0}: Connected successfully.".format(self.firewall_config['name']))
		rpc = etree.tostring(str(jns.rpc.get_security_policies_hit_count()), encoding='unicode')
		soup = BS(rpc,'xml')
		entries = list()
		for hitcount in soup.find('policy-hit-count').children:
			if type(hitcount) != Tag or hitcount.name != 'policy-hit-count-entry':
				continue
			aux = {
			'count' : int(hitcount.find('policy-hit-count-count').text),
			'from' : hitcount.find('policy-hit-count-from-zone').text,
			'to' : hitcount.find('policy-hit-count-to-zone').text,
			'policy' : hitcount.find('policy-hit-count-policy-name').text
			}
			entries.append(aux)
		return {'len' : len(entries), 'hitcount' : entries}