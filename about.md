The user can log in with their role(Donor, Hospital, or Blood bank)

# 1. Donor
They enter their information at initial signup; Last donation(days), Location, and Blood type . This information will, match them to the nearest hospitals needing blood, and will be used to decide if they are elligible to donate blood or not.

The user can register from the website or via USSD.

# 2. Hospital
The hospital also sets up their profile in a similar way, to get matched to nearest donors and blood banks.

In case of an emergency, the hospital enters the details about what is needed. This information is seen by the nearest donor(They will get information via email or SMS) who will be asked to go donate blood to the nearest hospital and all information will be peovided, if they have access to the website, they can contact the hospital from the website as the hospitals needing blood will be displayed here(via phone call). 

The donor conveys themselves to the hospital, donates the blood, the hospital conforms the donation from their dashboard, the donor gets loyalty points(to prioritize em in case they also need blood in the future) and a transportation reimbursement to cover their transportation cost to and fro the hosp.

Also the Blood bank will recieve a similar update on their dashboard and email and they can fullfill the request. If they do have the blood requested by the hospital nearest to them,they  click Fulfill on their dashboard, they send a dispatch rider(or any messenger) to deliver the blood, once the hospital recieves the blood they can marked it as recieved and the blood bank will see from their dashboard thet the hospital has successfully recieved the blood.

## Predictions
Instead of waiting until a crisis occurs, the hospital can get blood-demand predictions so they are prepared beforehand just in case. Various ML models (people call them AI-models which isn't wrong, but they are best refered to as Machine Learning models) are trained on the available hospital datasets to detect hospital patterns leading to blood demand. The best performing model is used to predict future blood demand based on the most recent data(preferrably 14 to 30 days). The blood demand prediction is explained on the dashboard in human-readable language(using AI).

The hospital uploads their dataset in csv format following the example schema provided. It's however not mandatory they stick to the schema, they could add other relevent dataset features that could help in training the models. The system's data pipeline handles that efficiently, so it's not a problem. The hospital will always have to upload the new datasets to the system once they have access to it. 

Since professionals need to understand why the AI made the predictions it did / not be in the dark(refered to as the black-box problem), I implemented smthng called SHAPLey Additive explanations(in short SHAP). This shows/explains the key drivers leading to predictions(top 5), eg if the predicted blood demand is 50 units, SHAP identifies which features in  the data contributed to this 50 units prediction and this could be for instance Blood Urgency Level. This helps the hsp. know why the model does what it does and why they hve the predicted blood demand.

# 3. The Blood bank
Their role is to fulfill blood demand for the hospitals closest to them. 
From their dashboard they update the available units per blood type to keep track of everything.
They fullfill blood requests by the hospitals as discussed earlier.

# Concerns 

Data security-- patient data is often regarded sensitive, but this isn't a problem since the data the hospital uploads to the system for prediction does not/must not contain any patient identification data.

Finances-- As you said Damu haiuzwi so the hospital will fund their mpesa account and only compensate for the donors transport costs. 

Platform-- This is a protoptype, the mobile application requires time to be actualized. So for smartphone users, the web works just fine for now. 

Dataset and Predictions-- ML models learn patterns in the data, so when actual hospital data is provided that will not be a problem, models will be retrained on that real data. This is a prototype and since real data could not be accessed, a simulated dataset is used instead.

# What is yet to be implemented
- USSD signups and functionality
- SMS automation(notifications)
- M-PESA automatic reimbursement(b2c-business to customer)

- Secure Identity Verification-- I shall later figure out a way to prevent fake donor registration. This is still not yet figured out for now
- Geolocation matching-- It's currently at county level for demonstration, but will later have it be based on distance (mobile phone location access), and preferably Constituency/Ward-level. 


**Other improvements in UI, architecture, and logic will be updated in time. Most cases when building such systems you always come across something you missed initially or new better ideas, so that isn't a problem.**




