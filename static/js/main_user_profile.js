
function user_profile()
{
    console.log('user_profile');
    var roles;
    
    $.post("/get_active_user_roles").done(function (response) {
        //console.log(response.state);
        //console.log(response.roles);
        roles = response;
        console.log("THE")
        //role = (x).toString().replace(/'/g, '"');
        //roles = JSON.parse(role);
        //console.log(roles);
        //console.log(roles['admin_check']);
        fin_flag=0
        instruc_flag=0
        if(roles['admin_check'] == 1) // Admin profile
            {
                $('.user_profile').each(function(j, obj) {
                    //console.log(j);
                    $(this).css('display','block');

                });
                fin_flag=1
                instruc_flag=1
                console.log("eshta")
                $.post("/get_finance_balance").done(function (response) {
                    console.log("HERE FINANCE BALANCE .. ")

                    bank = response.bank_balance
                    cash = response.cash_balance
                    console.log(bank,cash)
                    $('#all_finance_balance_cash').val(response.all_cash_balance) 
                    $('#all_finance_balance_bank').val(response.all_bank_balance) 
                    $('#finance_balance').val(response.balance)
                    $('#finance_balance_bank').val(bank)
                    $('#finance_balance_cash').val(cash) 
                    
                    $('#finance_money_in').val(response.finance_money_in)
                    $('#finance_money_out').val(response.finance_money_out)
                    $('#cash_money_in').val(response.cash_money_in)
                    $('#cash_money_out').val(response.cash_money_out)
                    console.log("AFTERO")
                    console.log(response.finance_money_in,response.finance_money_out,response.cash_money_in,response.cash_money_out)
                    
                })
                
                $.post("/get_employee_balance").done(function (response) {

        
                    $('#employee_balance').val(response.balance)

                })
                $.post("/get_admin_balance").done(function (response) {

        
                    $('#admin_balance').val(response.balance)

                })

                $.post("/get_instructor_money_out?get_all_balances").done(function (response) {

        
                    $('#instructor_balance').val(response.remaining)

                })

                    

                
                
                return false; // skip rest of profiles
            }

        
    jQuery.each(roles, function(i, val) {  // Rest of profiles
        //console.log(i)
        //console.log(val)
        
        if( val == 0) { return; }
        
        if(i == 'edu_user_check')
        {
            $("#home_nav").css('display','block');
            //$("#mobile_app_nav").css('display','block');
            $("#wallet_nav").css('display','block');
            $("#calendar_nav").css('display','block');
            $("#group_transfer_nav").css('display','block');
            $("#closing_instructor_nav").css('display','block');
            //$("#add_money_nav").css('display','block');
            $("#class_nav").css('display','block');
            $("#students_nav").css('display','block');
            $("#registeration_nav").css('display','block');
            $("#attendance_nav").css('display','block');
            $("#employees_nav").css('display','block');
            $("#employee_info").css('display','block');
            $("#inventory_nav").css('display','block');
            $.post("/get_employee_balance").done(function (response) {

        
                $('#employee_balance').val(response.balance)

            })

            if (fin_flag == 0)
            {
                $("#finance_info").css('display','block');
                
                fin_flag=1
                $.post("/get_finance_balance").done(function (response) {
    
            
                    bank = response.bank_balance
                    cash = response.cash_balance
                    $('#finance_balance').val(response.balance)
                    $('#finance_balance_bank').val(bank)
                    $('#finance_balance_cash').val(cash) 
                    $('#finance_money_in').val(response.finance_money_in)
                    $('#finance_money_out').val(response.finance_money_out)
                    $('#cash_money_in').val(response.cash_money_in)
                    $('#cash_money_out').val(response.cash_money_out)

                    
                })
            }
            if (instruc_flag == 0)
            {
                
                
                instruc_flag=1
                $.post("/get_instructor_money_out?get_all_balances").done(function (response) {

        
                    $('#instructor_balance').val(response.remaining)
    
                })
            }
            
        }

        if(i == 'cash_accountant_check')
        {
            
            $("#home_finance_nav").css('display','block');
            
            if (fin_flag == 0)
            {
                $(".finance_info").css('display', 'block');
                fin_flag=1

            }
            $.post("/get_finance_balance").done(function (response) {
                bank = response.bank_balance
                cash = response.cash_balance
                $('#finance_balance_cash').val(cash) 
        
                $('#finance_balance').val(response.balance)

                $('#cash_money_in').val(response.cash_money_in)
                $('#cash_money_out').val(response.cash_money_out)

                
            })
            
        }

        if(i == 'accountant_money_in_check')
        {
            $("#home_finance_nav").css('display','block');
            if (fin_flag == 0)
            {
                fin_flag=1

            }
            $(".finance_info").css('display', 'block');
                
            $.post("/get_finance_balance").done(function (response) {

        
                bank = response.bank_balance
                cash = response.cash_balance
                $('#finance_balance').val(response.balance)
                $('#finance_balance_bank').val(bank)
                
                $('#finance_money_in').val(response.finance_money_in)
                

                
            })
        }

        if(i == 'accountant_money_out_check')
        {
            $("#home_finance_nav").css('display','block');
            if (fin_flag == 0)
            {
                $(".finance_info").css('display', 'block');
                fin_flag=1

            }
            $.post("/get_finance_balance").done(function (response) {
    
                bank = response.bank_balance
                cash = response.cash_balance
                $('#finance_balance').val(response.balance)
                $('#finance_balance_bank').val(bank)

                $('#finance_money_out').val(response.finance_money_out)

                $('#cash_money_out').val(response.cash_money_out)

                
            })
        }

        if(i == 'finance_auditor_check')
        {
            $("#home_finance_nav").css('display','block');
        }

        if(i == 'hr_check')
        {
            $('#hr_nav').css('display','block');
        }


      });

    });




};