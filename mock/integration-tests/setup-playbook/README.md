Starting EC2 machine
--------------------

1. init git submodules

       git submodule update --init --recursive

2. setup AWS vars like this (change fields appropriately):

       cat > group_vars/all.yaml <<EOF
       ---
       aws:
         image: ami-004f552bba0e5f64f
         profile: fedora-copr  # you need credentials for this
         ssh_key: praiskup
         instance_type: t2.xlarge
         security_group: mock-testing
         root_volume_size: 60
         infra_subnet: subnet-09c74a3e6420a206b
       EOF

3. setup credentials/aws config:

       cat ~/.aws/config
       [profile fedora-copr]
       region = us-east-1
       output = table
       $ cast ~/.aws/

       cat ~/.aws/credentials
       [fedora-copr]
       aws_access_key_id=<the-key-id>
       aws_secret_access_key=<the-secret-key>

4. start the machine

       ansible-playbook spawn-test-machine-ec2.yaml

       PLAY [Start new machine] *******************

       TASK [create the testing mock vm in ec2] ***
       changed: [localhost]

       TASK [print ipv4] **************************
       ok: [localhost] => {
           "msg": [
               "Instance ID: i-02f769285490cbb64",
               "Network ID: eni-0298fa7a391ecc42e",
               "Unusable Public IP: 107.20.103.13"
           ]
       }

       PLAY RECAP ********************************
       localhost : ok=2 changed=1 unreachable=0 ...
