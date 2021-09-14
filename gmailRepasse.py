#coding: utf-8
import json
import time
import sys
#import sentry_sdk
import logging
#from sentry_sdk.integrations.logging import LoggingIntegration
from inspect import currentframe, getframeinfo
from pprint import pprint
from API_Atitude.api_trello_class import Trello_Board
from API_Atitude.portalAtitude import PortalAtitude
from API_Atitude.firebaseAtitude import FirebaseAtitude
from API_Atitude.x9 import x9, avisos_bots, send_erro_to_x9, log_msg
from API_Atitude.gmailAtitude import GmailAtitude
from datetime import datetime

logging.basicConfig(filename='myapp.log', format='%(asctime)s | %(levelname)s: %(message)s',  filemode="w",  level=20)

credentialsOpen = open('credentials.json')
credentials = json.load(credentialsOpen)
credentialsOpen.close()

try:
	projectAttadmin = FirebaseAtitude(credentials['CertAttadmin'], credentials['DataBaseUrlAttadmin'], "[DEFAULT]", credentials['BucketNameAttadmin'])
except:
	projectAttadmin = FirebaseAtitude(credentials['CertAttadmin'], credentials['DataBaseUrlAttadmin'], "attadmin", credentials['BucketNameAttadmin'])

firebaseIdLabels = projectAttadmin.get_info_db_realtime("idsTrelloOperacao/idLabels")
credsPortal = projectAttadmin.get_info_db_realtime("Credentials/Portal")

Portal = PortalAtitude(credsPortal['login'], credsPortal['senha'])

Gmail = GmailAtitude("token.pickle", "credsgmail.json")

config = {'apikey': credentials['ApiKey'], 'token': credentials['Token']}

TrelloAss = Trello_Board("Assinatura", config)
TrelloSC = Trello_Board("Sucesso do Cliente", config)
TrelloOp = Trello_Board("Operação", config)

INTERVAL = 20
INTERVAL_TRELLO = 5
TIMEOUT = 300
INTERVAL_GMAIL = 60

HORA_INICIO = 7
HORA_FIM = 21
FUSO = 3

def main():
	print("")
	horaBR = datetime.now().hour - FUSO
	# se hora - FUSO < 0, eh dia anterior, entao deve somar 24h ao resultado
	if horaBR < 0:
		horaBR = horaBR + 24

	if horaBR < HORA_INICIO or horaBR > HORA_FIM:
		print("NAO EH HORA DE RODAR O SCRIPT GMAIL REPASSE")
		print(horaBR)
	else:
		print("BUSCANDO emails ...")
		listIds = Gmail.get_emails_ids_list()
		if listIds == []:
			print('Nenhum email na caixa de entrada.')
		else:
			for emailId in listIds:
				print("=== e-mail id: {} ===".format(emailId))
				r = detail_email(emailId)
				print("*****************")
				print('status: {}. Aguardando {} segundos para repetir.'.format(r,INTERVAL))
				time.sleep(INTERVAL)


def detail_email(emailId):
	email = Gmail.get_email_by_id(emailId)
	emailLabels = Gmail.get_labels(email)
	if "INBOX" in emailLabels:
		# set variaveis
		labelsAdd = ["STARRED"]
		labelsDel = ["INBOX"]
		listName = "E-mails Repasse"
		dueDate = 2
	
		# get info do email
		headers = Gmail.get_headers(email)
		subject, rfcId, remetente, data = extrai_info_headers(headers)
		body = Gmail.extract_body_from_email(email)
		body = "(Remetente/Data) " + remetente + " " + data + "\n" + body
		snippet = Gmail.get_snippet(email)
		
		print("=== subject e snippet: ===")
		print(subject)
		print('-----')
		print(snippet)
		print('==========================')

		# valida regras de negocio e pode criar cartao em Op ou Sc
		response = business_rules(subject, body, snippet, remetente)
		print("1st response: {}".format(response))
		if response == 200:
			# nao precisa de outra tentativa
			retry = False
		elif response == 429: # too many requests
			retry = True
			time.sleep(10)	
		elif response == 431: #significa que o corpo do e-mail é muito grande para o trello
			print("response 431")
			#body = "O corpo deste e-mail é muito grande para o trello, favor verificar no gmail"
			body = snippet
			retry = True
		else:
			# outros erros diferentes dos acima, identificar e tratar
			retry = True

		# nova tentativa se retry for mudado para True
		if retry == True:
			print("response retry:" + str(response))
			time.sleep(INTERVAL_TRELLO)

			# segunda tentativa apos intervalo
			response = business_rules(subject, body, snippet, remetente)
			if response != 200: 
				body = snippet
				# tenta criar cartao com snippet
				cardId, response = TrelloSC.add_card_list_name(subject,body,listName,dueDate)
				if response != 200:
					# cria cartao basico
					body = "verifique corpo do email"
					cardId,response=TrelloSC.add_card_list_name(subject,body,listName,dueDate)

		# response == 200, criou o cartão entao pode alterar labels
		if response == 200:
			Gmail.change_labels_from_email(emailId, labelsAdd, labelsDel)
			print("labels do email alterados: {}".format(emailId))
		else:
			# todas as tentativas deram erro
			log_msg("erro na criação do cartão em GMAIL REPASSE, EmailId: {}".format(emailId))
			log_msg("gmailrepasse.py, subject: {}".format(subject))
		
		info = str(response) + " | " + str(subject)
		data = {'atualizacao': datetime.now(), 'status': 'online', 'info': info}
		projectAttadmin.update_collection_fc('botsStatus', 'gmailRepasse', data)

	return 'ok'


def business_rules(subject, body, snippet, remetente):
	CONFORME = subject.find("APOIO A PRODUÇÃO - CEHOP- CONCESSÃO HABITACIONAL - CONFORME")
	APROVADO1 = subject.find("PROPOSTA APROVADA - ATTITUDE SERVICOS EMPRESARIAIS LTDA")
	APROVADO2 = subject.find("PROPOSTA APROVADA - ATITUDE SERVICOS EMPRESARIAIS LTDA")
	FINAL_CONFORME = subject.find("CONTRATO FINALIZADO CONFORME")
	FINAL_INCONFORME = subject.find("CONTRATO FINALIZADO INCONFORME")
	PROPOSTA = subject.find("Proposta de crédito imobiliário")
	ARQ_ACEITO = subject.find("ARQUIVO DE IMAGEM ACEITO")
	CEHOP_INCONFORME = subject.find("APOIO A PRODUÇÃO - CEHOP - Inconforme")
	ARQ_REJEITADO = subject.find("ARQUIVO DE IMAGEM REJEITADO")
	PROP_PENDENTE = subject.find("PROPOSTA PENDENTE - ATTITUDE SERVICOS EMPRESARIAIS LTDA")
	EMAIL_LOGIN_CIWEB = subject.find(
		"[CIWEB/SISEG] Login no sistema, codigo de verificacao.")
	
	# srnorte@atitudesf.com.br | sroeste@atitudesf.com.br | srsul@atitudesf.com.br
	# ignorar mensagens dessas SR se não forem do código do CIWEB
	RMTE_SR_N = remetente.find('srnorte@atitudesf.com.br')
	RMTE_SR_O = remetente.find('sroeste@atitudesf.com.br')
	RMTE_SR_S = remetente.find('srsul@atitudesf.com.br')

	log_msg("inicio business rules", room='', channel='print e log')
	if CONFORME > -1 or APROVADO1 > -1 or APROVADO2 > -1:
		response = trata_conformidade(subject, body)
	elif FINAL_CONFORME > -1 or FINAL_INCONFORME > -1 or PROPOSTA > -1 or ARQ_REJEITADO > -1:
		log_msg("Final, proposta ou rejeitado: nao vai entrar no trello", room='', channel='print e log')
		response = 200
	elif ARQ_ACEITO > -1:
		response = trata_imagem_aceito(subject, body)
	elif CEHOP_INCONFORME > -1:
		listName = "Outros Repasse"
		dueDate = 2
		etiqueta = firebaseIdLabels["Inconformidade"]
		cardId, response = TrelloOp.add_card_list_name(subject, body, listName, dueDate, labels = etiqueta)
	elif PROP_PENDENTE > -1: #Inconformidade
		response = trata_inconformidade(subject, body)
	elif EMAIL_LOGIN_CIWEB > -1:
		response = busca_email_codigo(subject, body)
	else:
		if RMTE_SR_N > -1 or RMTE_SR_O > -1 or RMTE_SR_S > -1:
			# desabilitar a troca de lista, seria arquivar
			listName = "E-mails Repasse" #'Arquivar'
		else:
			listName = "E-mails Repasse"
		dueDate = 2
		cardId, response = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
		if response == 400:
			body = snippet #"O corpo deste email e muito grande para o trello"
			cardId, response = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
	print(response)
	print("end business_rules")
	return response
	#adicionar trello

def busca_email_codigo(subject,body):
	log_msg("busca email codigo")
	codigo, data_referencia = 'na','na'
	
	dueDate = 2
	etiqueta = ''
	cardId, statusCode = TrelloOp.add_card_list_name(
		subject, body, "E-mails Repasse", dueDate, labels=etiqueta)
	print(statusCode)

	lines_list = body.splitlines( )
	for line in lines_list:
		print(line)
		if "Codigo:" in line:
			codigo = line.split(":")[1].strip()
		if "Data de referencia" in line:
			data_referencia = line.split("a:")[1].strip()	
			data_referencia = data_referencia[:-1]
	
	data_ref_coll = data_referencia.replace(":","")
	data_ref_coll = data_ref_coll.replace("/","")
	data_ref_coll = data_ref_coll.replace(" ", "_")
	data = {'data_referencia': data_ref_coll, 'codigo': codigo}
	projectAttadmin.save_document_fc('codigo_ciweb', data_ref_coll, data)
	
	return 'ok'


def trata_inconformidade(subject, body):
	log_msg("trata inconformidade", room='', channel='print e log')
	codAntigo = "na"
	codPastaExterno = "na"
	cpf = "na"
	contrato = "na"
	lines = body.splitlines()
	for line in lines:
		if "CPF:" in line.upper():
			cpf = line.split(":")[1].strip()
			dictElementos = Portal.busca_cliente_by_cpf(cpf)
			print("trata inconformidade if CPF:")
			print(cpf)
			print(dictElementos)
			if type(dictElementos) == tuple:
				break
			codAntigo = dictElementos.get('cod_pasta', "na")
			if codAntigo == "na":
				print(dictElementos)
				erro = "O erro do Gmail repasse surgiu, vai la ver"
				frameinfo = getframeinfo(currentframe())
				send_erro_to_x9(frameinfo, erro)
			contrato = dictElementos['contrato']
			#codPastaExterno = dictElementos['cod_pasta_atual']
			break
	if codAntigo == "1157" or codAntigo == "1350": #4.02 e 4.05 respectivamente
		codStatus = "1125"
		codNovo = "1158" #4.03
		codSub = "109" #Outros
		if contrato == "na":
			statusCode = 400
		else:	
			statusCode = Portal.altera_status_cliente_by_contrato(contrato, codAntigo, codStatus, codNovo, codSub)
		if statusCode == 200:
			listName = "Outros Repasse"
			dueDate = 2
			etiqueta = firebaseIdLabels['Inconformidade']
			cardId, statusCode = TrelloOp.add_card_list_name(subject, body, listName, dueDate, labels = etiqueta)
			return statusCode
		else:
			return 400
	elif codAntigo == "1158": #esse é o 4.03
		return 200
	elif len(cpf) != 11:
		return 400
	elif codAntigo != "1157" and codAntigo != "1350":
		#aviso = "O cliente a seguir chegou no e-mail de CEHOP inconforme, porem estava no status de " + str(codPastaExterno) + "\nhttps://atitudesf.portalderepasse.com.br/v3/contrato_detalhe.asp?contrato=" + str(contrato)
		#avisos_bots(aviso)
		listName = "Outros Repasse"
		dueDate = 2
		etiqueta = firebaseIdLabels['Inconformidade']
		cardId, statusCode = TrelloOp.add_card_list_name(subject, body, listName, dueDate, labels = etiqueta)
		return statusCode
	else:
		listName = "E-mails Repasse"
		dueDate = 2
		cardId, statusCode = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
		return statusCode

def trata_imagem_aceito(subject, body):
	log_msg("trata imagem aceito", room='', channel='print e log')
	codAntigo = "na"
	codPastaExterno = "na"
	inicio = str(body).upper().find(".PDF") - 2
	final = inicio + 2
	status = body[inicio:final]
	inicio = body.find("_") + 1
	final = inicio + 11
	cpf = body[inicio:final]
	print(status)
	print("Este e o cpf encontrado: " + str(cpf))
	if status.upper() == "PR" or status.upper() == "CP" or status.upper() == "RV":
		print("if 1")
		dictElementos = Portal.busca_cliente_by_cpf(cpf)
		print(dictElementos)
		if type(dictElementos) == tuple:
			listName = "E-mails Repasse"
			dueDate = 2
			cardId, statusCode = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
			return statusCode
		contrato = dictElementos.get('contrato', "na")
		if contrato == "na":
			print(dictElementos)
			erro = "O erro do Gmail repasse surgiu, vai la ver"
			log_msg(str(cpf))
			log_msg("nao achou contrato no portal")
			log_msg(subject)
			#frameinfo = getframeinfo(currentframe())
			#send_erro_to_x9(frameinfo, erro)
		codStatus = "1125"
		cod_pasta = dictElementos.get('cod_pasta','na') 
		if cod_pasta == "1156":
			# 4.01 -> 4.02
			codAntigo = "1156"
			codNovo = "1157"
		elif cod_pasta == "1349":
			# 4.04 -> 4.05
			codAntigo = "1349"
			codNovo = "1350"
		elif cod_pasta in ["1157", "1350"]:
			return 200
		else:
			listName = "E-mails Repasse"
			dueDate = 2
			cardId, statusCode = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
			return statusCode
		statusCode = Portal.altera_status_cliente_by_contrato(contrato, codAntigo, codStatus, codNovo)
		#alteração de status no portal
		print("Status code: " + str(statusCode))
		return statusCode
	elif status.upper() == "GR":
		print("elif trataimagem")
		return 200
	else:
		print("else trataimagem")
		listName = "E-mails Repasse"
		dueDate = 2
		cardId, statusCode = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
		return statusCode

def trata_conformidade(subject, body):
	log_msg("trata conformidade", room='', channel='print e log')
	codAntigo = "na"
	codPastaExterno = "na"
	contrato, cpf = "na", "na"
	lines = body.splitlines()
	for line in lines:
		if "CPF:" in line.upper():
			cpf = line.split(":")[1].strip()
			dictElementos = Portal.busca_cliente_by_cpf(cpf)
			if dictElementos is None:
				print('possivel erro de login no portal')
				time.sleep(5)
			if type(dictElementos) == tuple:
				print("E uma tupla, quebrou o for, nao pode mais vir nenhum print de conformidade")
				log_msg("retorno portal: {}".format(str(dictElementos)))
				break
			codAntigo = dictElementos.get('cod_pasta', "na")
			if codAntigo == "na":
				print(dictElementos)
				print("contrato nao encontrado no portal")
				erro = "Gmail Repasse, contrato NAO encontrado no portal{}".format(cpf)
				frameinfo = getframeinfo(currentframe())
				send_erro_to_x9(frameinfo, erro)
			contrato = dictElementos['contrato']
			codPastaExterno = dictElementos.get('cod_pasta_atual','na')
			break
	if codAntigo == "1157" or codAntigo == "1350": #4.02 e 4.05 respectivamente
		codStatus = "1126"
		codNovo = "1159"
		statusCode = Portal.altera_status_cliente_by_contrato(contrato, codAntigo, codStatus, codNovo)
		return statusCode
	elif codAntigo == "1159": #esse é o 5.01
		return 200
	elif len(cpf) != 11:
		print("CPF Errado")
		return 400
	elif "5" in codPastaExterno:
		print("Já esta em assinatura")
		return 200
	else:
		listName = "E-mails Repasse"
		dueDate = 2
		cardId, statusCode = TrelloSC.add_card_list_name(subject, body, listName, dueDate)
		log_msg("trata conformidade, cartao criado {}".format(cardId), room='', channel='print e log')
		return statusCode

def extrai_info_headers(headers):
	subject, rfcId, remetente, data = "na", "na", "na", "na"
	for header in headers:
		if str(header['name']).upper()=="SUBJECT":
			subject = header['value']
		elif str(header['name']).upper()=="MESSAGE-ID":
			rfcId = header['value']
		elif str(header['name']).upper()=="FROM":
			remetente = header['value']
		elif str(header['name']).upper()=="DATE":
			data = header['value']
			data = data[0:len(data)-5]

	return subject, rfcId, remetente, data

if __name__ == "__main__":
	while True:
		try:
			main()
			print("-----------------------------------")
			print("aguardando intervalo de {} segundos".format(INTERVAL_GMAIL))
			print(str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
			print("-----------------------------------")
			#data = {'atualizacao': datetime.now(), 'status': 'online', 'info': 'em execução'}
			time.sleep(INTERVAL_GMAIL)
		except Exception as e:
			data = {'atualizacao': datetime.now(), 'status': 'except', 'info': str(e)}
			log_msg(str(e))
			projectAttadmin.update_collection_fc('botsStatus', 'gmailRepasse', data)
			
