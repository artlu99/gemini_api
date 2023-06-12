from gemini import PrivateClient

import pandas as pd
import PySimpleGUI as sg

# TODO: read from ini or json file
CONST_BASE_CCY = 'USD'
CONST_WATCHLIST = ['BTC', 'ETH', 'LUNA', 'CRV', 'AXS']
CONST_PUBLIC_KEY = 'account-xxxxxxxxxxxxxxxxxxxx'
CONST_QTY_ROUND = 6  # TODO: include

symbol, symbol_pair, amt, exec_price, side, api_call = 'ETH', 'ETHUSD', '0.01', '1.0', 'buy', 'None'


def update_balances(obj_ptr):
    get_balance = obj_ptr.get_balance()
    assert type(get_balance) is list
    balances_df = pd.DataFrame(get_balance)[
        ['currency', 'available']].set_index('currency')
    balances_df = balances_df.reindex(
        sorted(set(balances_df.index.tolist() + CONST_WATCHLIST))).fillna(0)
    balances_df['currency'] = balances_df.index
    return balances_df


if __name__ == "__main__":
    private_key = sg.popup_get_text(
        'Gemini Trading API private key', password_char='*')
    if private_key is None:
        exit("API key not provided")

    # TODO: make the connection a button and a state
    public_key = CONST_PUBLIC_KEY
    rp = PrivateClient(public_key, private_key, sandbox=False)
    heartbeat_status = rp.revive_hearbeat()
    assert type(heartbeat_status) is dict
    if heartbeat_status['result'] == 'error':
        exit(f"{heartbeat_status['reason']}: {heartbeat_status['message']}")
    assert heartbeat_status['result'] == 'ok'

    balances_df = update_balances(rp)

    sg.theme('Dark Blue 3')
    layout = [
        [sg.Table(values=balances_df.values.tolist(), headings=['trading balance', 'currency'],
                  justification='right', num_rows=6, enable_events=True,
                  key='-BALANCES-'),
         sg.Table(values=[[None, None]], headings=['bid', 'ask'],
                  display_row_numbers=False, auto_size_columns=False, num_rows=6,
                  key='-BIDOFFER-')
         ],
        [sg.Input(default_text=symbol_pair, key='-symbol_pair-', size=(10, 1)),
         sg.Input(default_text=amt, key='-amt-', size=(10, 1)),
         sg.Input(default_text=exec_price,
                  key='-exec_price-', size=(10, 1)),
         sg.Radio('buy', key='-buy-', group_id='-side-', default=True),
         sg.Radio('sell', key='-sell-',
                  group_id='-side-', default=False),
         sg.Text(key='-DOLLAR-')
         ],
        [sg.Button('Build'), sg.StatusBar('api call', size=(
            45, 1), key='-STATUS-'), sg.Button('Send Order')],
        [sg.Text('Blotter')], [sg.Multiline(
            size=(72, 5), key='-BLOTTER-')],
    ]
    window = sg.Window('Gemini API GUI', layout)

    while True:  # Event Loop
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break

        if values['-buy-']:
            side = 'buy'
        elif values['-sell-']:
            side = 'sell'

        if event == '-BALANCES-':    # balances table gets clicked on
            symbol = balances_df.iat[values['-BALANCES-'][0], 1]
            if symbol == CONST_BASE_CCY:
                continue
            symbol_pair = symbol + CONST_BASE_CCY

            # live bid-offer
            ticker_md_dict = rp.get_ticker(symbol_pair)
            window['-BIDOFFER-'].update(
                [[bo for bo in [ticker_md_dict['bid'], ticker_md_dict['ask']]]])

            window['-symbol_pair-'].update(symbol_pair)

            if float(balances_df.at[symbol, 'available']) > 0:
                window['-exec_price-'].update(ticker_md_dict['bid'])
                window['-amt-'].update(balances_df.at[symbol, 'available'])
                side = 'sell'
                window['-buy-'].update(False)
                window['-sell-'].update(True)
            else:
                window['-exec_price-'].update(ticker_md_dict['ask'])
                window['-amt-'].update(amt)
                side = 'buy'
                window['-buy-'].update(True)
                window['-sell-'].update(False)

            # TODO: this is dup'd
            window['-DOLLAR-'].update(round(float(values['-amt-'])
                                      * float(values['-exec_price-']), 2))
        elif event == 'Build':
            # TODO: this is dup'd
            window['-DOLLAR-'].update(round(float(values['-amt-'])
                                      * float(values['-exec_price-']), 2))

            api_call = f"rp.new_order('{values['-symbol_pair-'].lower()}', '{values['-amt-']}', '{values['-exec_price-']}', '{side}', [])"
            window['-STATUS-'].update(api_call)
        elif event == 'Send Order':
            sg.popup_quick_message(api_call, background_color='red')

            res = rp.new_order(values['-symbol_pair-'].lower(),
                               values['-amt-'], values['-exec_price-'], side, [])
            assert type(res) is dict, type(res)
            if 'message' in res.keys():
                blotter = res.get('message')
            else:
                blotter = f"{res['type']}: {res['side']} {res['symbol']} at {res['price']}"
            window['-BLOTTER-'].update(blotter + '\n', append=True)

            balances_df = update_balances(rp)
            window['-BALANCES-'].update(balances_df.values.tolist())

    window.close()
