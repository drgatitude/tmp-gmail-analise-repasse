#coding: utf-8
import api_gmail as ag
import api_trello as at
import api_firebase as afb
import parametrosConfiguracao as pc
from pprint import pprint
from datetime import datetime, timedelta, date, timezone
import pytz
from x9 import x9
import time
from pprint import pprint
from bs4 import BeautifulSoup
from datetime import datetime
import sys
# tmux a -t gmailanalise

FUSO = 3
LISTABASE = 'E-mails'
LISTA_ARQUIVAR = 'Arquivar'

import config_settings as cs

EMAILS = cs.EMAILS
DANIEL = cs.DANIEL
BOARDOPERACAO = cs.BOARDOPERACAO
BOARDIDTESTE = cs.BOARDIDTESTE
LISTTESTE = cs.LISTTESTE

ChecklistTESTEID = cs.ChecklistTESTEID

EMAIL_SRNORTE = cs.EMAIL_SRNORTE
EMAIL_SROESTE = cs.EMAIL_SROESTE
EMAIL_SRSUL = cs.EMAIL_SRSUL

# quadro TrelloTest
DANIELTESTE = cs.DANIELTESTE
EMAILSTESTE = cs.EMAILSTESTE
FINALIZADOSTESTE = cs.FINALIZADOSTESTE


USE = 'TESTE'
if sys.platform == 'linux' or sys.platform == 'linux2':
    USE = 'PRODUCAO'

if USE == 'TESTE':
    USELIST = EMAILSTESTE
    BOARDID = BOARDIDTESTE
elif USE == 'PRODUCAO':
    USELIST = EMAILS
    BOARDID = BOARDOPERACAO
elif USE == 'TESTEOPERACAO' :
    USELIST = DANIEL
    BOARDID = BOARDOPERACAO
else:
    USELIST = DANIEL
    BOARDID = BOARDOPERACAO

listid = USELIST

SMALL_BREAK = 20
BIG_BREAK = 400


def main():
    while True:
        print("main loop")
        try:
            datenow = datetime.now()
            print(datenow)
            #if datenow.hour > 8:
            mainloop()
        except Exception as e:
            print("===================x====================")
            print("===================x====================")
            x9('EXCEPT MAIN LOOP: ' +str(e))
            data = {'atualizacao': datetime.now(), 'status': 'except', 'info': str(e)}
            afb.update_collection_fc('botsStatus', 'gmailAnalise', data)
            print("===================x====================")
            print("===================x====================")
        time.sleep(SMALL_BREAK)


def mainloop():
    consultasInbox = 0
    cardsCreated = 0
    emailsRead = 0
    labelsModified = 0
    while True:
        start_time = time.time()
        time.sleep(SMALL_BREAK)
        rstatus_code = 0
        qtdMsgThread = 0

        collection = 'msgidcardid' + datetime.now().strftime('%Y%m%d')
        collectionexcept = 'msgidcardidEXCEPT' + datetime.now().strftime('%Y%m%d')
        cardid, subject, remetente, dataEnvio = 'na', 'na', 'na','na'
        msg, msg_id, msgidinfo = 'na', 'na', 'na'
        messageId, content = 'na', 'na'
        cpfcliente, etapaSafi = 'na', 'na'
        qtdAttachments = 0
        classificacao = 'na'
        # Pega todas as 100 primeiras mensagens que estao no INBOX no momento da consulta
        # depois faz um loop (for) por essas mensagens
        # quando o for acabar, volta para o while para verificar se ha novas mensagens
        listIds = ag.get_listof_msgid_threadid_from_inbox()
        consultasInbox += 1
        print('listIds: ' + str(listIds))
        print(len(listIds))
        print("---------------------------------------------------------------------")
        datenow = datetime.now()
        print(datenow)
        print('cartoes criados: {}; emails lidos: {}; emails arquivados: {}.'.format(cardsCreated, emailsRead,
                                                                                     labelsModified))
        print("---------------------------------------------------------------------")
        try:
            data = {'atualizacao': datetime.now(), 'status': 'online'}
            afb.update_collection_fc('botsStatus', 'gmailAnalise', data)
        except Exception as e:
            print("except atualizando firebase" + str(e))
        time.sleep(1)
        for item in listIds:
            print("---------------------------------------------------------------------")
            print("---------------------------------------------------------------------")
            print('cartoes criados: {}; emails lidos: {}; emails arquivados: {}.'.format(cardsCreated,emailsRead,labelsModified))
            print("---------------------------------------------------------------------")
            print("---------------------------------------------------------------------")
            if cardsCreated != emailsRead or labelsModified != emailsRead:
                desc = str(subject) + str(msg_id)
                at.add_card('ERRO NA SEQUENCIA DOS CARTOES - ULTIMOS DADOS:',desc)
            try:
                time.sleep(2)
                # PEGA msg_id e thread_id para tratar a mensagem #
                msg_id = item['id'] #listIds[0]['id']
                threadid = item['threadId'] #listIds[0]['threadid']

                # mensagens desta thread para ver a quantidade de mensagens na thread #
                try:
                    threadsmsgs = ag.get_thread_messages_by_threadid(threadid)
                    qtdMsgThread = len(threadsmsgs)
                    if qtdMsgThread > 1: # mensagem anterior da thread, caso exista
                        prev_msgid = ag.get_previous_msg_id_by_threadid(threadid)
                        print('mais de uma mensagem')
                        if prev_msgid == 'na':
                            print("primeiro email da thread")
                        else:
                            print("make function to get previous cardid")
                            # depois add coment no cartao com a mensagem ou se o cartao ja estiver arquivado, cria novo e coloca a referencia nele
                except Exception as e:
                    print('====EXCEPT THREADS=====')
                    time.sleep(2)
                    x9('except threads: ' + str(e))
                try:
                    ### PEGA O JSON DA MENSAGEM ###
                    msg = ag.get_message_by_msgid(msg_id)
                    ### GET HEADERS ###
                    subject, remetente, messageId, content, dataEnvio = ag.get_headers_info_from_msg(msg)
                    msgidinfo = "rfc822msgid:" + messageId
                    emailsRead += 1
                    qtdAttachments = ag.count_msg_atachments(msg)
                    #pprint(msg)
                except Exception as e:
                    print('====EXCEPT MSG=====')
                    time.sleep(2)
                    x9('except get_msg_by_msgid: '+str(e))
                try:
                    body = ag.get_body_msg_excepts(msg)
                except Exception as e:
                    print(e)
                    print('==========EXCEPT BODY ONE========')
                    try:
                        body = ag.get_textplain_body_msg(msg)
                    except Exception as e:
                        print(e)
                        print("==========EXCEPT BODY TWO========")
                        try:
                            body = ag.get_body_msg(msg)
                            body = BeautifulSoup(body, "lxml").text
                        except Exception as e:
                            print('==========EXCEPT BODY THREE========')
                            print(e)
                            time.sleep(2)
                            body = 'ERRO GET BODY' + str(e)

                corpo = 'msg_id:' + msg_id + "\n(Remetente/Data) " + remetente + " " + dataEnvio + "\n" + body
                corpo = set_body(corpo)

                #pprint(body)
                try:
                    listName, label, prazoHoras, posicaoNaListaTrello,classificacao, cpfcliente, etapaSafi = pc.get_parametros(remetente,subject, body)
                    #return lista, label, prazoHoras, posicaoNaListaTrello, classificacao, cpf, etapa
                    duedate = set_duedate(prazoHoras)
                    print('Informacoes: {};{};{};{};{}'.format(subject, remetente, msgidinfo, content, dataEnvio))
                except Exception as e:
                    print(f'**************** Exception: {str(e)}')
                    label, prazoHoras, posicaoNaListaTrello, classificacao = '','2','bottom','na'
                    listName = LISTABASE
                    duedate = set_duedate(prazoHoras)

                if 'SAFI - Processo para Análise de Crédito' in subject:
                    # id label Safi
                    label = '6061f6d3c3000d6cbdbe1428'

                # E-mails das SR Norte, Oeste, Sul que não venham com o código, devem ser criados na lista Arquivar.
                EMAIL_LOGIN_CIWEB = subject.find("[CIWEB/SISEG] Login no sistema, codigo de verificacao.")
                if EMAIL_LOGIN_CIWEB > -1:
                    print('email com codigo de login do ciweb, criar cartao na lista padrao')
                else:
                    # criar cartao na lista Arquivar porque nao é sobre código do CIWEB
                    if EMAIL_SRNORTE in remetente or EMAIL_SROESTE in remetente or EMAIL_SRSUL in remetente:
                        listName = LISTA_ARQUIVAR

                #name, desc, pos = 'bottom', duedate = '', labels = 'na', listid = USELIST)
                try:
                    #cardid, rstatus_code = at.add_card(subject, corpo, posicaoNaListaTrello,duedate,label)
                    print('======================informacoes=====================')
                    print(f'list name: {listName}')
                    print(f'label, prazo, posicao: {label};{prazoHoras};{posicaoNaListaTrello}')
                    print(f'cpf: {cpfcliente}')
                    print('=========================fim info=============================')
                    time.sleep(2)
                    cardid, rstatus_code = at.add_card_list_name(subject, corpo, listName, duedate, posicaoNaListaTrello, label)
                    print(f'1st attempt: cardid,rstatuscode: {str(cardid)},{str(rstatus_code)}')
                    time.sleep(3)
                    if cardid == 'no label found for id':
                        # labelId invalido, criar cartao sem label:
                        print("===LABEL NOT FOUND===")
                        time.sleep(3)
                        #cardid, rstatus_code = at.add_card(subject, corpo, posicaoNaListaTrello, duedate, '')
                        cardid,rstatus_code=at.add_card_list_name(subject,corpo,listName,duedate,posicaoNaListaTrello,'')
                    elif rstatus_code == 400:
                        corpo = 'msg_id:' + msg_id + " (Remetente/Data) " + remetente + " " + dataEnvio + ";" + \
                                'MSG SNIPPET: ' + msg.get("snippet")
                        #cardid, rstatus_code = at.add_card(subject, corpo, posicaoNaListaTrello, duedate, label)
                        cardid, rstatus_code = at.add_card_list_name(subject,corpo,listName,duedate,posicaoNaListaTrello,
                                                                     label)
                        if cardid == 'no label found for id':
                            #cardid, rstatus_code = at.add_card(subject, corpo, posicaoNaListaTrello, duedate, '')
                            cardid, rstatus_code = at.add_card_list_name(subject,corpo,listName,duedate,posicaoNaListaTrello,'')
                    print('em 1 ==========================================')
                except Exception as e:
                    print("===EXCEPT CRIA CARTAO===")
                    print(e)
                    corpo = 'msg_id:' + msg_id + " (Remetente/Data) " + remetente + " " + dataEnvio + ";"
                    corpo = corpo + 'MSG SNIPPET: ' + msg.get("snippet")
                    try:
                        print("===SNIPPET:" + corpo)
                        time.sleep(2)
                        # listid definido no inicio desse arquivo
                        cardid, rstatus_code = at.add_card(subject, corpo, listid, duedate,posicaoNaListaTrello, label)
                        print('2 ==========================================')
                    except Exception as e:
                        print("===EXCEPT CRIA CARTAO II===")
                        print(e)
                        corpo = 'erro na criacao do cartao '+ msgidinfo
                        cardid, rstatus_code = at.add_card(subject, corpo,listid,duedate,posicaoNaListaTrello,label)
                        print('3 ==========================================')

                if rstatus_code == 200: # Nao Criou cartao, criar com condicoes minimas
                    cardsCreated += 1
                else:
                    print(str(rstatus_code))
                    time.sleep(3)
                    try:
                        corpo = 'MENSAGEM TRUNCADA: ' + msg.get("snippet")
                        cardid, rstatus_code = at.add_card(subject, corpo)
                        if rstatus_code == 200:
                            cardsCreated += 1
                        else:
                            corpo = 'erro para criar o cartao: ' + msgidinfo
                            cardid, rstatus_code = at.add_card(subject, corpo)
                            if rstatus_code == 200:
                                cardsCreated += 1
                            else:
                                x9("cartao nao criado: {}".format(str(msg_id)))
                    except Exception as e:
                        print('====EXCEPT FOUR=====')
                        print(e)
                        time.sleep(2)
                        x9("cartao nao criado: " + msg_id)
                if rstatus_code == 200:
                    try:
                        r = ag.remove_inbox_unread_labels(msg_id)
                        print(r)
                        labelsModified +=1
                    except Exception as e:
                        print(e)
                    try:
                        data = {'msgid': msg_id,
                                'cardid': cardid,
                                'subject': subject,
                                'msgidinfo': msgidinfo,
                                'threadid': threadid,
                                'snippet': msg.get("snippet"),
                                'qtdAttachments': qtdAttachments,
                                'qtdMsg': qtdMsgThread
                                }
                        r1 = afb.save_info_firestore(collection, msg_id, data)
                        print(r1)
                    except Exception as e:
                        print(e)
                        x9("except save firestore: " + str(msg_id))
                    try:
                        at.add_comment(cardid,msgidinfo)
                        comment = 'Esse e o {} email da thread e tem {} anexos'.format(str(qtdMsgThread),
                                                                                   str(qtdAttachments))
                        #at.add_comment(cardid,comment)
                        if classificacao != 'na':
                            at.add_comment(cardid, classificacao)
                        if cpfcliente != 'na':
                            texto = 'CPF: ' + str(cpfcliente) #+"; etapa: " + etapaSafi
                            at.add_comment(cardid, texto)
                        at.add_comment(cardid, f'CardID: {cardid}')
                    except Exception as e:
                        print(e)
                        print('====EXCEPT ADD COMMENTS=====')
                        time.sleep(2)

                time.sleep(1)
                final_time = time.time()
                print("Tempo rodando: " + str(final_time - start_time))

                try:
                    info = str(emailsRead) + "|" + subject[:30]
                    data = {'atualizacao': datetime.now(), 'status': 'online', 'info': info}
                    afb.update_collection_fc('botsStatus', 'gmailAnalise', data)
                except Exception as e:
                    print("except atualizando firebase" + str(e))

            except Exception as e:
                print(e)
                x9(e)
                print('====EXCEPT LOOP FOR CARTAO PODE NAO TER SIDO CRIADO=====')
                try:
                    r1 = afb.save_info_cardid_msgid(collectionexcept, cardid, msg_id, subject, msgidinfo)
                    print(r1)
                except:
                    x9("except LOOP FOR save firebase: " + str(msg_id))
                    x9(str(subject))
        #print("end loop for")
        nowutc = datetime.now(timezone.utc)
        nowLocal = nowutc - timedelta(hours=FUSO)
        print("in regular loop")
        if nowLocal.hour < 8:
            print("waiting {}...".format(BIG_BREAK))
            time.sleep(BIG_BREAK)

def set_body(corpo):
    corpo = corpo.replace("Wed,", "Qua,")
    corpo = corpo.replace(" Dec ", " Dez ")
    corpo = corpo.replace("\\r", "\r")
    corpo = corpo.replace("\\n", "\n")
    tamFinal = len(corpo) - 1
    corpo = corpo[:tamFinal]
    return corpo

def set_duedate(prazoHoras):
    nowutc = datetime.now(timezone.utc)
    #print(nowutc)
    nowlocal = nowutc - timedelta(hours=FUSO)
    timezonesp = pytz.timezone('America/Sao_Paulo')
    #print(nowlocal)
    print(f'due date prazoHoras:{prazoHoras}')
    try:
        prazo = int(prazoHoras)
    except Exception as e:
        print(f'Except duedate prazoHoras: {str(e)}')
        prazo = 2
    if nowlocal.hour > 19:
        print("d+1 9h + prazo")
        date = datetime(nowlocal.year, nowlocal.month, nowlocal.day, 9 + prazo, 0, 0, tzinfo=timezonesp) + timedelta(days=1)
        duedate = date #datetime(nowlocal.year, nowlocal.month, nowlocal.day + 1, 9 + prazo, 0, 0, tzinfo=timezonesp)
    elif nowlocal.hour < 9:
        duedate = datetime(nowlocal.year, nowlocal.month, nowlocal.day, 9 + prazo, 0, 0, tzinfo=timezonesp)
        print("9h + prazo")
    else:
        print("local hour + prazo")
        duedate = datetime(nowlocal.year, nowlocal.month, nowlocal.day, nowlocal.hour + prazo, nowlocal.minute, 0,
                           tzinfo=timezonesp)
    print(duedate)
    return(duedate)

if __name__=='__main__':
    main()
