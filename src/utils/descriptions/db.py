db_tag_description = "Сервисные операции с базой данных."

db_init_description = (
    """
    **Инициализация БД.**<br>
    <br>
    1. Создание справочника ролей.<br>
    2. Создание первого суперадмина.<br>
    3. Создание справочника типов карт.<br>
    <br>
    **Входные параметры (передаются в теле запроса):**<br>
    <br>
    **service_token** - сервисный токен, указанный в главном конфигурационном 
    файле (**.env**).<br>
    **superuser_password** - пароль для первого суперадмина (логин - **cargo**).
    """
)

db_initial_sync_description = (
    """
    Коннектор для первичной синхронизации локальной БД с БД основной площадки. Прогружаются следующие данные.<br>
    <br>
    1. Системы.<br>
    2. Тарифы.<br>
    3. Организации.<br>
    4. Автомобили.<br>
    5. Топливные карты.<br>
    6. Товары / услуги.<br>
    7. Транзакции.<br>
    <br>
    **Входные параметры (передаются в теле запроса):**<br>
    <br>
    **service_token** - сервисный токен, указанный в главном конфигурационном файле (**.env**).<br>
    <br>
    **systems** - список систем в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"id":&emsp;<идентификатор записи>,<br>
            &emsp;&emsp;"full_name":&emsp;<полное наименование системы>,<br>
            &emsp;&emsp;"short_name":&emsp;<краткое наименование системы>,<br>
            &emsp;&emsp;"login":&emsp;<логин доступа>,<br>
            &emsp;&emsp;"password":&emsp;<пароль>,<br>
            &emsp;&emsp;"transaction_days":&emsp;<кол-во дней для получения последних транзакций от системы><br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    **tariffs** - список тарифов в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"id":&emsp;<идентификатор записи>,<br>
            &emsp;&emsp;"title":&emsp;<наименование>,<br>
            &emsp;&emsp;"service_online":&emsp;<комиссия за обслуживание, %>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    **companies** - список организаций в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"id":&emsp;<идентификатор записи>,<br>
            &emsp;&emsp;"name":&emsp;<наименование>,<br>
            &emsp;&emsp;"date_add":&emsp;<дата создания записи>,<br>
            &emsp;&emsp;"rate_id":&emsp;<идентификатор тарифа>,<br>
            &emsp;&emsp;"inn":&emsp;<ИНН>,<br>
            &emsp;&emsp;"amount":&emsp;<текущий баланс, руб>,<br>
            &emsp;&emsp;"min_balance":&emsp;<постоянный овердрафт, руб>,<br>
            &emsp;&emsp;"min_balance_period":&emsp;<временный овердрафт, руб>,<br>
            &emsp;&emsp;"min_balance_date_to":&emsp;<временный овердрафт, дата прекращения>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    **cars** - список автомобилей в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"id":&emsp;<идентификатор записи>,<br>
            &emsp;&emsp;"company_id":&emsp;<идентификатор организации>,<br>
            &emsp;&emsp;"car_number":&emsp;<гос. номер>,<br>
            &emsp;&emsp;"driver_name":&emsp;<водитель>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    **cards** - список топливных карт в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"system_id":&emsp;<идентификатор системы поставщика услуг>,<br>
            &emsp;&emsp;"state":&emsp;<состояние карты: активна/заблокирована>,<br>
            &emsp;&emsp;"card_num":&emsp;<номер карты>,<br>
            &emsp;&emsp;"company_id":&emsp;<идентификатор организации>,<br>
            &emsp;&emsp;"car_id":&emsp;<идентификатор автомобиля>,<br>
             &emsp;&emsp;"manual_lock":&emsp;<признак ручной блокировки>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    **goods** - список товаров/услуг в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"system_id":&emsp;<идентификатор системы поставщика услуг>,<br>
            &emsp;&emsp;"outer_goods":&emsp;<наименование в системе поставщика услуг>,<br>
            &emsp;&emsp;"inner_goods":&emsp;<наименование в локальной системе>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    **transactions** - список транзакций в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"id":&emsp;<идентификатор транзакции>,<br>
            &emsp;&emsp;"date":&emsp;<время транзакции в системе поставщика услуг>,<br>
            &emsp;&emsp;"date_load":&emsp;<время прогрузки в локальную систему>,<br>
            &emsp;&emsp;"type":&emsp;<тип транзакции>,<br>
            &emsp;&emsp;"system_id":&emsp;<идентификатор системы поставщика услуг>,<br>
            &emsp;&emsp;"company_id":&emsp;<идентификатор организации>,<br>
            &emsp;&emsp;"address":&emsp;<адрес АЗС>,<br>
            &emsp;&emsp;"fuel_type":&emsp;<тип топлива>,<br>
            &emsp;&emsp;"volume":&emsp;<объем топлива, литры>,<br>
            &emsp;&emsp;"price":&emsp;<цена, руб>,<br>
            &emsp;&emsp;"sum":&emsp;<сумма транзакции>,<br>
            &emsp;&emsp;"sum_service":&emsp;<размер комисии за обслуживание>,<br>
            &emsp;&emsp;"total":&emsp;<итоговая сумма для списания со счета>,<br>
            &emsp;&emsp;"balance":&emsp;<баланс организации после транзакции>,<br>
            &emsp;&emsp;"comment":&emsp;<комментарии>,<br>
            &emsp;&emsp;"gds":&emsp;<товар (не топливо)/услуга>,<br>
            &emsp;&emsp;"azs":&emsp;<код АЗС>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    """
)

db_regular_sync_description = (
    """
    Коннектор для регулярной синхронизации локальной БД с БД основной площадки. Прогружаются следующие данные:<br>
    <br>
    1. Организации.<br>
    <br>
    **Входные параметры (передаются в теле запроса):**<br>
    <br>
    **service_token** - сервисный токен, указанный в главном конфигурационном файле (**.env**).<br>
    <br>
    **companies** - список организаций в формате<br>
    <i>
    [<br>
        &emsp;{<br>
            &emsp;&emsp;"id":&emsp;<идентификатор записи>,<br>
            &emsp;&emsp;"name":&emsp;<наименование>,<br>
            &emsp;&emsp;"date_add":&emsp;<дата создания записи>,<br>
            &emsp;&emsp;"inn":&emsp;<ИНН>,<br>
            &emsp;&emsp;"amount":&emsp;<текущий баланс, руб>,<br>
            &emsp;&emsp;"min_balance":&emsp;<постоянный овердрафт, руб>,<br>
            &emsp;&emsp;"min_balance_period":&emsp;<временный овердрафт, руб>,<br>
            &emsp;&emsp;"min_balance_date_to":&emsp;<временный овердрафт, дата прекращения>,<br>
        &emsp;},<br>
        &emsp;...<br>
    ]<br>
    </i><br>
    """
)
