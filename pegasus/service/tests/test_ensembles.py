from pegasus.service import tests, ensembles, api, db
from pegasus.service.ensembles import *

class TestEnsembles(tests.TestCase):
    def test_name(self):
        validate_ensemble_name("x"*99)
        validate_ensemble_name("ensemble12")
        validate_ensemble_name("ensemble.12")
        validate_ensemble_name("ensemble_12")
        validate_ensemble_name("ensemble-12")
        self.assertRaises(api.APIError, validate_ensemble_name, "x"*100)
        self.assertRaises(api.APIError, validate_ensemble_name, None)
        self.assertRaises(api.APIError, validate_ensemble_name, "foo/bar/baz")
        self.assertRaises(api.APIError, validate_ensemble_name, "../foo")
        self.assertRaises(api.APIError, validate_ensemble_name, "foo/../foo")

    def test_ensemble_states(self):
        self.assertEquals(EnsembleStates.ACTIVE, "ACTIVE")
        self.assertTrue("ACTIVE" in EnsembleStates)

    def test_priority(self):
        self.assertEquals(validate_priority(10), 10)
        self.assertEquals(validate_priority(10.1), 10)
        self.assertEquals(validate_priority(10.6), 10)
        self.assertEquals(validate_priority("10"), 10)
        self.assertRaises(api.APIError, validate_priority, "a")
        self.assertRaises(api.APIError, validate_priority, "10.1")

    def test_write_planning_script(self):
        f = StringIO()
        write_planning_script(f, tcformat="tc", rcformat="rc", scformat="sc",
                              sites=["local"], output_site="local",
                              staging_sites={"a":"b", "c":"d"},
                              clustering=["horizontal","vertical"],
                              force=True, cleanup=False)
        script = f.getvalue()
        self.assertTrue("#!/bin/bash" in script)
        self.assertTrue("pegasus-plan" in script)
        self.assertTrue("-Dpegasus.catalog.site=sc" in script)
        self.assertTrue("-Dpegasus.catalog.site.file=sites.xml" in script)
        self.assertTrue("-Dpegasus.catalog.transformation=tc" in script)
        self.assertTrue("-Dpegasus.catalog.transformation.file=tc.txt" in script)
        self.assertTrue("-Dpegasus.catalog.replica=rc" in script)
        self.assertTrue("-Dpegasus.catalog.replica.file=rc.txt" in script)
        self.assertTrue("--conf pegasus.properties" in script)
        self.assertTrue("--site local" in script)
        self.assertTrue("--output-site local" in script)
        self.assertTrue("--staging-site a=b,c=d" in script)
        self.assertTrue("--cluster horizontal,vertical" in script)
        self.assertTrue("--force" in script)
        self.assertTrue("--nocleanup" in script)
        self.assertTrue("--dir submit" in script)
        self.assertTrue("--dax dax.xml" in script)

        f = StringIO()
        write_planning_script(f, tcformat="tc", rcformat="rc", scformat="sc",
                              sites=["local"], output_site="local")
        script = f.getvalue()
        self.assertFalse("--staging-site" in script)
        self.assertFalse("--cluster" in script)
        self.assertFalse("--force" in script)
        self.assertFalse("--nocleanup" in script)

        f = StringIO()
        write_planning_script(f, tcformat="tc", rcformat="rc", scformat="sc",
                              sites=["local"], output_site="local",
                              staging_sites={"a":"b"},
                              clustering=["horiz"], force=False,
                              cleanup=True)
        script = f.getvalue()
        self.assertTrue("--staging-site a=b " in script)
        self.assertTrue("--cluster horiz" in script)
        self.assertFalse("--force" in script)
        self.assertFalse("--nocleanup" in script)

class TestEnsembleDB(tests.UserTestCase):
    def test_ensemble_db(self):
        self.assertEquals(len(ensembles.list_ensembles(self.user_id)), 0, "Should be no ensembles")
        e = ensembles.create_ensemble(self.user_id, "foo", 1, 1)
        self.assertEquals(len(ensembles.list_ensembles(self.user_id)), 1, "Should be 1 ensemble")

class TestEnsembleAPI(tests.APITestCase):
    def test_ensemble_api(self):
        r = self.get("/ensembles")
        self.assertEquals(r.status_code, 200)
        self.assertEquals(len(r.json), 0, "Should not be any ensembles")

        r = self.post("/ensembles")
        self.assertEquals(r.status_code, 400, "Should fail on missing ensemble params")

        r = self.post("/ensembles", data={"name":"myensemble"})
        self.assertEquals(r.status_code, 201, "Should return created status")
        self.assertTrue("location" in r.headers, "Should have location header")

        r = self.get("/ensembles/myensemble")
        self.assertEquals(r.status_code, 200)
        self.assertEquals(r.json["name"], "myensemble", "Should be named myensemble")
        self.assertEquals(r.json["state"], EnsembleStates.ACTIVE, "Should be in active state")
        self.assertEquals(len(r.json["workflows"]), 0, "Should not have any workflows")

        # Need to sleep for one second so that updated gets a different value
        updated = r.json["updated"]
        import time
        time.sleep(1)

        r = self.get("/ensembles")
        self.assertEquals(r.status_code, 200, "Should return 200 OK")
        self.assertEquals(len(r.json), 1, "Should be one ensemble")

        update = {
            "state": EnsembleStates.HELD,
            "max_running": "10",
            "max_planning": "2"
        }
        r = self.post("/ensembles/myensemble", data=update)
        self.assertEquals(r.status_code, 200, "Should return OK")
        self.assertEquals(r.json["state"], EnsembleStates.HELD, "Should be in held state")
        self.assertEquals(r.json["max_running"], 10, "max_running should be 10")
        self.assertEquals(r.json["max_planning"], 2, "max_planning should be 2")
        self.assertNotEquals(r.json["updated"], updated)

    def test_ensemble_workflow_api(self):
        r = self.post("/ensembles", data={"name": "myensemble"})
        self.assertEquals(r.status_code, 201, "Should return created status")

        r = self.get("/ensembles/myensemble/workflows")
        self.assertEquals(r.status_code, 200, "Should return OK")
        self.assertEquals(len(r.json), 0, "Should have no workflows")

        # Create some test catalogs
        catalogs.save_catalog("replica", self.user_id, "rc", "regex", StringIO("replicas"))
        catalogs.save_catalog("site", self.user_id, "sc", "xml4", StringIO("sites"))
        catalogs.save_catalog("transformation", self.user_id, "tc", "text", StringIO("transformations"))
        db.session.commit()

        # Create a test workflow
        req = {
            "name":"mywf",
            "priority":"10",
            "site_catalog": "sc",
            "transformation_catalog": "tc",
            "replica_catalog":"rc",
            "dax": (StringIO("my dax"), "my.dax"),
            "conf": (StringIO("my props"), "pegasus.properties"),
            "args": (StringIO("""
            {
                "sites": ["local"],
                "output_site": "local"
            }
            """), "args.json")
        }
        r = self.post("/ensembles/myensemble/workflows", data=req)
        self.assertEquals(r.status_code, 201, "Should return CREATED")
        self.assertTrue("location" in r.headers, "Should have location header")

        # Make sure all the files were created
        wfdir = os.path.join(self.tmpdir, "userdata/scott/ensembles/myensemble/workflows/mywf")
        self.assertTrue(os.path.isfile(os.path.join(wfdir, "sites.xml")))
        self.assertTrue(os.path.isfile(os.path.join(wfdir, "dax.xml")))
        self.assertTrue(os.path.isfile(os.path.join(wfdir, "rc.txt")))
        self.assertTrue(os.path.isfile(os.path.join(wfdir, "tc.txt")))
        self.assertTrue(os.path.isfile(os.path.join(wfdir, "pegasus.properties")))
        self.assertTrue(os.path.isfile(os.path.join(wfdir, "plan.sh")))

        r = self.get("/ensembles/myensemble")
        self.assertEquals(r.status_code, 200, "Should return OK")
        self.assertEquals(len(r.json["workflows"]), 1, "Should have 1 workflow")

        r = self.get("/ensembles/myensemble/workflows")
        self.assertEquals(r.status_code, 200, "Should return OK")
        self.assertEquals(len(r.json), 1, "Should have one workflow")

        r = self.get("/ensembles/myensemble/workflows/mywf")
        self.assertEquals(r.status_code, 200, "Should return OK")
        self.assertEquals(r.json["name"], "mywf", "Name should be mywf")
        self.assertEquals(r.json["priority"], 10, "Should have priority 10")
        self.assertEquals(r.json["state"], EnsembleWorkflowStates.READY, "Should have state READY")
        self.assertTrue("wf_uuid" in r.json)
        self.assertTrue("dax" in r.json)
        self.assertTrue("conf" in r.json)
        self.assertTrue("sites" in r.json)
        self.assertTrue("replicas" in r.json)
        self.assertTrue("plan_script" in r.json)

        for f in ["dax.xml","pegasus.properties","sites.xml","rc.txt","tc.txt","plan.sh"]:
            r = self.get("/ensembles/myensemble/workflows/mywf/%s" % f)
            self.assertEquals(r.status_code, 200, "Should return OK")
            self.assertTrue(len(r.data) > 0, "File should not be empty")

        r = self.post("/ensembles/myensemble/workflows/mywf", data={"priority":"100"})
        self.assertEquals(r.status_code, 200, "Should return OK")
        self.assertEquals(r.json["priority"], 100, "Should have priority 100")

class TestEnsembleClient(tests.ClientTestCase):

    def test_ensemble_client(self):
        cmd = ensembles.EnsembleCommand()

        cmd.main(["list"])
        stdout, stderr = self.stdio()
        self.assertEquals(stdout, "", "Should be no stdout")

        cmd.main(["create","-n","foo","-P","20","-R","30"])
        stdout, stderr = self.stdio()
        self.assertEquals(stdout, "", "Should be no stdout")

        cmd.main(["list"])
        stdout, stderr = self.stdio()
        self.assertEquals(len(stdout.split("\n")), 3, "Should be two lines of stdout")

        cmd.main(["update","-e","foo","-P","50","-R","60"])
        stdout, stderr = self.stdio()
        self.assertTrue("Name: foo" in stdout, "Name should be foo")
        self.assertTrue("Max Planning: 50" in stdout, "Max Planning should be 50")
        self.assertTrue("Max Running: 60" in stdout, "Max running should be 60")

        cmd.main(["pause","-e","foo"])
        stdout, stderr = self.stdio()
        self.assertTrue("State: PAUSED" in stdout, "State should be paused")

        cmd.main(["hold","-e","foo"])
        stdout, stderr = self.stdio()
        self.assertTrue("State: HELD" in stdout, "State should be held")

        cmd.main(["activate","-e","foo"])
        stdout, stderr = self.stdio()
        self.assertTrue("State: ACTIVE" in stdout, "State should be active")

        # Create some test catalogs using the catalog API
        catalogs.save_catalog("replica", self.user_id, "rc", "regex", StringIO("replicas"))
        catalogs.save_catalog("site", self.user_id, "sc", "xml4", StringIO("sites"))
        catalogs.save_catalog("transformation", self.user_id, "tc", "text", StringIO("transformations"))
        db.session.commit()

        cmd.main(["submit","-e","foo","-n","bar","-d","setup.py",
                  "-T","tc","-R","rc","-S","sc","-s","local",
                  "-o","local","--staging-site","ss=s,s2=s",
                  "-C","horiz,vert","-p","10","-c","setup.py"])
        stdout, stderr = self.stdio()
        self.assertEquals(stdout, "")

