
function fin_user_profile()
{
    console.log('fin_profile');

    var roles;
    
    $.post("/get_active_user_roles").done(function (response) {
        //console.log(response.state);
        //console.log(response.roles);
        roles = response;
        //role = (x).toString().replace(/'/g, '"');
        //roles = JSON.parse(role);
        //console.log(roles);
        //console.log(roles['admin_check']);

        if(roles['admin_check'] == 1) // Admin profile
            {
                $('.fin_profile').each(function(j, obj) {
                    //console.log(j);
                    $(this).css('display','block');
                });
                
                return false; // skip rest of profiles
            }

        
    jQuery.each(roles, function(i, val) {  // Rest of profiles
        //console.log(i)
        //console.log(val)

        if( val == 0) { return; }


        if(i == 'cash_accountant_check')
        {
            $("#cash_approval_div").css('display','block');
            $("#customers_div").css('display','block');
        }

        if(i == 'accountant_money_in_check')
        {
            $("#add_money_in_div").css('display','block');
            $("#approve_money_in_div").css('display','block');
            //$("#fiannce_report_div").css('display','block');
            $("#add_cost_div").css('display','block');
            $("#add_sub_cost_div").css('display','block');
            $("#transfer_money_div").css('display','block');
            $("#customers_div").css('display','block');
        }

        if(i == 'accountant_money_out_check')
        {
            $("#add_money_out_div").css('display','block');
            $("#approve_money_out_div").css('display','block');
            //$("#fiannce_report_div").css('display','block');
            $("#add_cost_div").css('display','block');
            $("#add_sub_cost_div").css('display','block');
            $("#transfer_money_div").css('display','block');
            $("#customers_div").css('display','block');
        }

        if(i == 'finance_auditor_check')
        {
            $("#audit_page_div").css('display','block');
            $("#fiannce_report_div").css('display','block');
            $("#customers_div").css('display','block');
        }


      });

    });

};