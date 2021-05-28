# coding: utf-8

"""Conversion handlers for the ROS geometry_msgs package."""

import warnings

import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    import quaternion

from numpy_ros.conversions import converts_to_numpy, converts_to_message, to_numpy

try:
    from geometry_msgs.msg import (
        Accel, AccelStamped, AccelWithCovariance, AccelWithCovarianceStamped,
        Inertia, InertiaStamped, Point, Point32, PointStamped, Polygon, 
        PolygonStamped, Pose, PoseStamped, Quaternion, QuaternionStamped, 
        Transform, TransformStamped, Twist, 
        TwistStamped, TwistWithCovariance, TwistWithCovarianceStamped, Vector3, 
        Vector3Stamped, Wrench, WrenchStamped,
    )

except ImportError:
    raise ImportError(
        'Could not import geometry_msgs. Is the ROS package installed?'
    )

_stamped_type_to_attr = {
    AccelStamped: 'accel',
    AccelWithCovarianceStamped: 'accel',
    InertiaStamped: 'inertia',
    PointStamped: 'point',
    PolygonStamped: 'polygon',
    PoseStamped: 'pose',
    QuaternionStamped: 'quaternion',
    TransformStamped: 'transform',
    TwistStamped: 'twist',
    TwistWithCovarianceStamped: 'twist',
    Vector3Stamped: 'vector',
    WrenchStamped: 'wrench',
}


def _unstamp(message):
    """Unstamps a given message."""
    attr_name = _stamped_type_to_attr.get(message.__class__)
    
    if attr_name:
        message = getattr(message, attr_name)

    return message


def _assert_is_castable(array, dtype):
    """Checks that every element of the array can be converted to the desired
    dtype, without loss of precision."""

    min_dtype = np.min_scalar_type(array)

    if not np.can_cast(min_dtype, dtype):
        raise TypeError(f'Cannot safely cast array {array} to dtype {dtype}.')


@converts_to_numpy(Vector3, Vector3Stamped, Point, PointStamped, Point32)
def vector_to_numpy(message, homogeneous=False):
    """Converts 3d vector mesage types to a flat array."""

    message = _unstamp(message)

    data = [message.x, message.y, message.z]

    if homogeneous:
        data.append(1.0)

    dtype = np.float32 if isinstance(message, Point32) else np.float64
    array = np.array(data, dtype=dtype)

    return array


@converts_to_message(Vector3, Point, Point32)
def numpy_to_vector(message_type, array):
    """Converts a 3d vector representation to a ROS message"""

    if array.shape not in ((3,), (4,)):
        raise ValueError(
            f'Expected array of shape (3,) or (4,), received {array.shape}.'
        )

    dtype = np.float32 if message_type is Point32 else np.float64
    _assert_is_castable(array, dtype)
    
    if len(array) == 4 and not np.isclose(array[3], 1.0):
        raise ValueError(
            (f'Input array has four components, but last component is '
             f'{array[3]:.2} != 1.')
        )

    return message_type(*array[:3])


@converts_to_numpy(
    Accel, 
    AccelStamped, 
    Twist, 
    TwistStamped, 
    Wrench, 
    WrenchStamped
)
def kinematics_to_numpy(message, homogeneous=False):

    message = _unstamp(message)

    is_wrench = isinstance(message, Wrench)

    linear_message = message.force if is_wrench else message.linear
    angular_message = message.torque if is_wrench else message.angular

    linear = vector_to_numpy(linear_message, homogeneous=homogeneous)
    angular = vector_to_numpy(angular_message, homogeneous=homogeneous)

    return linear, angular


@converts_to_message(Accel, Twist, Wrench)
def numpy_to_kinamatics(message_type, linear, angular):

    is_wrench = message_type is Wrench

    linear_key = 'force' if is_wrench else 'linear'
    angular_key = 'torque' if is_wrench else 'angular'

    kwargs = {
        linear_key: numpy_to_vector(linear),
        angular_key: numpy_to_vector(angular)
    }

    return message_type(**kwargs)


@converts_to_numpy(
    AccelWithCovariance,
    AccelWithCovarianceStamped,
    TwistWithCovariance,
    TwistWithCovarianceStamped,
)
def kinematics_with_covariance_to_numpy(message, homogeneous=False):
    
    message = _unstamp(message)

    is_accel = isinstance(message, AccelWithCovariance)
    kinematics_message = message.accel if is_accel else message.twist

    linear, angular = kinematics_to_numpy(
        kinematics_message, 
        homogeneous=homogeneous
    )

    covariance = np.array(message.covariance, dtype=np.float64).reshape(6, 6)

    return linear, angular, covariance


@converts_to_message(AccelWithCovariance, TwistWithCovariance)
def numpy_to_kinematics_with_covariance(
    message_type, 
    linear, 
    angular, 
    covariance
    ):

    is_accel = message_type is AccelWithCovariance
    
    kinematics_key = 'accel' if is_accel else 'twist'
    kinematics_message_type = Accel if is_accel else Twist

    kinematics_message = numpy_to_kinamatics(
        kinematics_message_type, 
        linear,
        angular
    )

    covariance_message = numpy_to_covariance(covariance)

    kwargs = {
        kinematics_key: kinematics_message,
        'covariance': covariance_message
    }

    return message_type(**kwargs)


def numpy_to_covariance(array):

    _assert_is_castable(array, np.float64)

    if array.shape != (6,6):
        raise ValueError(
            (f'Expected covariance matrix of shape (6,6), received '
             f'{array.shape}.')
        )

    return tuple(array.flatten())


@converts_to_numpy(Inertia, InertiaStamped)
def inertia_to_numpy(message, homogeneous=False):
    
    message = _unstamp(message)

    mass = message.m
    mass_center = vector_to_numpy(message.com, homogeneous=homogeneous)
    inertia_tensor = np.array([
        [message.ixx, message.ixy, message.ixz],
        [message.ixy, message.iyy, message.iyz],
        [message.ixz, message.iyz, message.izz],
    ])

    return mass, mass_center, inertia_tensor


@converts_to_message(Inertia)
def numpy_to_inertia(message_type, mass, mass_center, inertia_tensor):

    _assert_is_castable(mass, np.float64)
    _assert_is_castable(inertia_tensor, np.float64)
    
    mass_center_message = numpy_to_vector(Vector3, mass_center)

    if inertia_tensor.shape != (3, 3):
        raise ValueError(
            (f'Expected inertia tensor of shape (6,6), received '
             f'{inertia_tensor.shape}.')
        )

    return message_type(
        m = float(mass),
        com = mass_center_message,
        ixx = inertia_tensor[0, 0],
        ixy = inertia_tensor[0, 1],
        ixz = inertia_tensor[0, 2],
        iyy = inertia_tensor[1, 1],
        iyz = inertia_tensor[2, 1],
        izz = inertia_tensor[2, 2]
    )


@converts_to_numpy(Polygon, PolygonStamped)
def polygon_to_numpy(message, homogeneous=False):
    
    message = _unstamp(message)

    points = np.array(
        [vector_to_numpy(p, homogeneous=homogeneous) for p in message.points], 
        dtype=np.float32
    )

    return points.T


@converts_to_message(Polygon)
def numpy_to_polygon(message_type, points):

    _assert_is_castable(points, np.float32)

    if points.ndim != 2 or len(points) not in (3, 4):
        raise ValueError(
            (f'Expected matrix of shape (3, *) or (4, *), received '
             f'{points.shape}.')
        )

    points_msg = []

    for point in np.hsplit(points, points.shape[1]):
        point_msg = numpy_to_vector(Point32, point.squeeze())
        points_msg.append(point_msg)

    return message_type(points_msg)


@converts_to_numpy(Quaternion, QuaternionStamped)
def quaternion_to_numpy(message):
    
    message = _unstamp(message)
    return np.quaternion(message.x, message.y, message.z, message.w)


@converts_to_message(Quaternion)
def numpy_to_quaternion(message_type, numpy_obj):

    if isinstance(numpy_obj, quaternion.quaternion):
        return message_type(*quaternion.as_float_array(numpy_obj))

    _assert_is_castable(numpy_obj, np.float64)

    if numpy_obj.shape != (4,):
        raise ValueError(
            f'Expected array of shape (4,), received {numpy_obj.shape}.'
        )

    return message_type(*(float(x) for x in numpy_obj))


@converts_to_numpy(Pose, PoseStamped, Transform, TransformStamped)
def frame_to_numpy(message, homogeneous=False):

    message = _unstamp(message)

    is_pose = isinstance(message, Pose)

    position_message = message.position if is_pose else message.translation
    rotation_message = message.orientation if is_pose else message.rotation

    position = vector_to_numpy(position_message, homogeneous=homogeneous)
    rotation = quaternion_to_numpy(rotation_message)

    if homogeneous:
        as_matrix = np.eye(4, dtype=np.float64)

        as_matrix[:, 3] = position
        as_matrix[:3, :3] = quaternion.as_rotation_matrix(rotation)

        return as_matrix

    return position, rotation


@converts_to_message(Pose, PoseStamped, Transform, TransformStamped)
def numpy_to_frame(message_type, *args):

    is_pose = message_type is Pose

    position_key = 'position' if is_pose else 'translation'
    rotation_key = 'orientation' if is_pose else 'rotation'

    if len(args) == 1:

        matrix = args[0]

        _assert_is_castable(matrix, Pose)

        if not matrix.shape == (4,4):
            raise ValueError(
                (f'Expected homogeneous matrix of shape (4,4), received '
                 f'{matrix.shape}.')
            )

        if not matrix[3, :] == np.array([0.0, 0.0, 0.0, 1.0]):
            raise ValueError(f'{matrix} is not a homogeneous matrix.')

        position = matrix[3, :]
        rotation = quaternion.from_rotation_matrix(matrix[:3, :3])

    elif len(args) == 2:
        position, rotation = args

    else:
        raise ValueError(
            (f'Expected either position (np.ndarray of length 3 or 4) and '
             f'rotation (np.quaternion) or homogeneous transform'
             f'(4x4 np.ndarray), received {args}.')
        )

    kwargs = {
        position_key: numpy_to_vector(position),
        rotation_key: numpy_to_quaternion(rotation)
    }

    return message_type(**kwargs)