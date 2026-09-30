import unittest
import test_verify
import verify_v2

# Run the same ten independent corruption/feasibility cases against v2.
test_verify.verify=verify_v2


class VerificationV2Tests(test_verify.VerificationTests):
    def test_unstable_clock_body_is_retained_but_never_usable(self):
        r=self.record();r['response_received_ns']+=6_000_000_000;r['wall_clock_stable']=False
        self.assertIsNone(verify_v2.decode_record(r,verify_v2.ENDPOINTS[0],0))
    def test_backward_clock_body_never_usable(self):
        r=self.record();r['response_received_ns']=99;r['wall_clock_stable']=False
        self.assertIsNone(verify_v2.decode_record(r,verify_v2.ENDPOINTS[0],0))


if __name__=='__main__':unittest.main()
