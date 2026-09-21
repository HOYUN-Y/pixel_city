import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import dense_seams as ds


class DenseSeamsTest(unittest.TestCase):
    def test_deterministic_connected_path(self):
        cost=np.ones((20,30)); cost[:,12]=0
        path=ds.minimum_path(cost)
        np.testing.assert_array_equal(path,12)
        np.testing.assert_array_equal(path,ds.minimum_path(cost))
        self.assertTrue((np.abs(np.diff(path))<=1).all())

    def test_blocked_path_is_not_relaxed(self):
        cost=np.zeros((10,20)); cost[4]=np.inf
        with self.assertRaisesRegex(ValueError,'No safe'): ds.minimum_path(cost)

    def test_horizontal_transpose_and_single_source_pixels(self):
        rng=np.random.default_rng(4)
        a=rng.integers(0,256,(70,40,3),dtype=np.uint8)
        b=rng.integers(0,256,a.shape,dtype=np.uint8)
        mask,_=ds.seam_mask(a,b)
        other,_=ds.seam_mask(a.transpose(1,0,2),b.transpose(1,0,2),axis=0)
        np.testing.assert_array_equal(mask,other.T)
        out=np.where(mask[:,:,None],b,a)
        self.assertTrue((np.all(out==a,axis=2)|np.all(out==b,axis=2)).all())

    def test_protected_ownership(self):
        a=np.zeros((60,80,3),dtype=np.uint8); b=a+100
        old=np.zeros((60,80),bool); old[20:40,15:22]=True
        new=np.zeros_like(old); new[20:40,32:45]=True
        mask,_=ds.seam_mask(a,b,force_old=old,force_new=new)
        self.assertTrue(mask[new].all()); self.assertFalse(mask[old].any())
        with self.assertRaises(ValueError): ds.seam_mask(a,b,force_old=new,force_new=old)

    def test_bounded_repair(self):
        a=np.zeros((100,100,3),dtype=np.uint8); b=a+255
        mask=np.zeros((100,100),bool); mask[20:40,30:60]=True
        out=ds.bounded_repair(a,b,mask)
        np.testing.assert_array_equal(out[~mask],a[~mask])
        np.testing.assert_array_equal(out[mask],b[mask])
        with self.assertRaises(ValueError): ds.bounded_repair(a,b,np.ones_like(mask))
        soft=ds.bounded_repair(a,b,mask,feather=4)
        np.testing.assert_array_equal(soft[~mask],a[~mask])
        self.assertEqual(int(soft[20,30,0]),64)
        self.assertEqual(int(soft[25,35,0]),255)
        with self.assertRaises(ValueError): ds.bounded_repair(a,b,mask,feather=5)

    def test_four_way_junction_coverage_and_native_ownership(self):
        rng=np.random.default_rng(5)
        tiles={(r,c):rng.integers(0,256,(48,48,3),dtype=np.uint8) for r in range(3) for c in range(3)}
        out,owner,coverage,reports=ds.mosaic(tiles,rows=3,columns=3,core=32,halo=8)
        self.assertEqual(len(reports),12)
        self.assertTrue((coverage>0).all()); self.assertTrue((owner>=0).all())
        self.assertEqual(int(coverage.max()),4)
        for (r,c),im in tiles.items():
            yy,xx=np.where(owner==r*3+c)
            np.testing.assert_array_equal(out[yy,xx],im[yy-r*32+8,xx-c*32+8])
        second=ds.mosaic(tiles,rows=3,columns=3,core=32,halo=8)
        np.testing.assert_array_equal(out,second[0]); np.testing.assert_array_equal(owner,second[1])

    def test_missing_tile_and_bad_forced_owner_rejected(self):
        tiles={(0,0):np.zeros((48,48,3),np.uint8)}
        with self.assertRaises(ValueError): ds.mosaic(tiles,rows=1,columns=2,core=32,halo=8)
        with self.assertRaises(ValueError): ds.mosaic(tiles,rows=1,columns=1,core=32,halo=8,forced=np.ones((32,32),np.int16))

    def test_protected_owner_survives_later_neighbors(self):
        tiles={(r,c):np.full((48,48,3),r*3+c,dtype=np.uint8) for r in range(3) for c in range(3)}
        force=np.full((96,96),-1,np.int16); force[60:62,60:62]=4
        out,owner,_,_=ds.mosaic(tiles,rows=3,columns=3,core=32,halo=8,forced=force)
        np.testing.assert_array_equal(owner[60:62,60:62],4)
        np.testing.assert_array_equal(out[60:62,60:62],4)


if __name__=='__main__': unittest.main()
